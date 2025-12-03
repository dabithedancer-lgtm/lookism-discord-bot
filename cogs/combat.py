import discord
import random
from difflib import get_close_matches
from discord.ext import commands
from discord.ui import View, Button, button
from utils.database import load, save
from utils.game_math import compute_stats

USERS_FILE = "data/users.json"
CARDS_FILE = "data/cards.json"
GANGS_FILE = "data/gangs.json"
RARITIES_FILE = "data/rarities.json"
BOSS_FILE = "data/bosses.json"


class BattleView(View):
    """Interactive battle view with card selection buttons"""

    def __init__(self, ctx, my_team, en_team, target, ensure_user_func):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.my_team = my_team
        self.en_team = en_team
        self.target = target
        self.ensure_user = ensure_user_func
        self.turn = 0
        self.max_turns = 15
        self.my_team_battle = [{"name": c["name"], "atk": c["atk"],
                                "hp": c["hp"], "max_hp": c["max_hp"]} for c in my_team]
        self.en_team_battle = [{"name": c["name"], "atk": c["atk"],
                                "hp": c["hp"], "max_hp": c["max_hp"]} for c in en_team]
        self.log = []
        self.battle_active = True
        self.msg = None

        # Create buttons for each card (1-4)
        for i in range(min(len(my_team), 4)):  # Max 4 cards
            self.add_item(CardAttackButton(i + 1, my_team[i]['name'], i))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
            return False
        if not self.battle_active:
            await interaction.response.send_message("❌ Battle has ended!", ephemeral=True)
            return False
        return True

    async def process_attack(self, interaction, card_index):
        """Process an attack from selected card"""
        if card_index < 0 or card_index >= len(self.my_team_battle):
            await interaction.response.send_message("❌ Invalid card selection!", ephemeral=True)
            return

        attacker = self.my_team_battle[card_index]
        if attacker['hp'] <= 0:
            await interaction.response.send_message("❌ This card is already defeated!", ephemeral=True)
            return

        # Find alive enemy
        p2_alive = [c for c in self.en_team_battle if c['hp'] > 0]
        if not p2_alive:
            await interaction.response.defer()
            await self.end_battle(True)
            return

        # Attack
        defender = random.choice(p2_alive)
        dmg = int(attacker['atk'] * (0.8 + random.random() * 0.4))
        defender['hp'] = max(0, defender['hp'] - dmg)
        hp_percent = int((defender['hp'] / defender['max_hp'])
                         * 100) if defender['max_hp'] > 0 else 0
        self.log.append(
            f"🔵 **{attacker['name']}** → **{defender['name']}** `{dmg}` dmg ({hp_percent}% HP)")

        # Enemy counter-attack
        p1_alive = [c for c in self.my_team_battle if c['hp'] > 0]
        if p1_alive and any(c['hp'] > 0 for c in self.en_team_battle):
            enemy_atk = random.choice(
                [c for c in self.en_team_battle if c['hp'] > 0])
            my_def = random.choice(p1_alive)
            enemy_dmg = int(enemy_atk['atk'] * (0.8 + random.random() * 0.4))
            my_def['hp'] = max(0, my_def['hp'] - enemy_dmg)
            my_hp_percent = int(
                (my_def['hp'] / my_def['max_hp']) * 100) if my_def['max_hp'] > 0 else 0
            self.log.append(
                f"🔴 **{enemy_atk['name']}** → **{my_def['name']}** `{enemy_dmg}` dmg ({my_hp_percent}% HP)")

        self.turn += 1

        # Check win conditions
        p1_alive = [c for c in self.my_team_battle if c['hp'] > 0]
        p2_alive = [c for c in self.en_team_battle if c['hp'] > 0]

        if not p1_alive or not p2_alive or self.turn >= self.max_turns:
            await interaction.response.defer()
            await self.end_battle(any(c['hp'] > 0 for c in self.my_team_battle))
        else:
            # Update embed
            await self.update_battle_embed(interaction)

    async def update_battle_embed(self, interaction):
        """Update battle embed with current state"""
        p1_alive = [c for c in self.my_team_battle if c['hp'] > 0]
        p2_alive = [c for c in self.en_team_battle if c['hp'] > 0]

        embed = discord.Embed(
            title="⚔️ Battle in Progress!",
            description=(
                f"**Turn {self.turn}**\n\n"
                f"🔵 **{self.ctx.author.display_name}'s Team** 🆚 🔴 **{self.target.display_name}'s Team**"
            ),
            color=0xF1C40F
        )
        # Left side: attacker (author) avatar via author icon
        embed.set_author(name="Player vs Player Battle",
                         icon_url=self.ctx.author.display_avatar.url)
        # Right side: defender avatar via thumbnail
        embed.set_thumbnail(url=self.target.display_avatar.url)

        my_team_text = "\n".join([
            f"• **{c['name']}** (Strength: {c['atk']} | Health: {c['hp']}/{c['max_hp']})"
            for c in self.my_team_battle
        ])
        en_team_text = "\n".join([
            f"• **{c['name']}** (Strength: {c['atk']} | Health: {c['hp']}/{c['max_hp']})"
            for c in self.en_team_battle
        ])

        embed.add_field(
            name=f"🔵 {self.ctx.author.display_name}'s Team",
            value=my_team_text,
            inline=True
        )
        embed.add_field(
            name=f"🔴 {self.target.display_name}'s Team",
            value=en_team_text,
            inline=True
        )

        if self.log:
            recent_log = "\n".join(self.log[-5:])
            embed.add_field(name="📋 Recent Actions",
                            value=recent_log, inline=False)

        embed.set_footer(text="Choose a card button below to attack!")

        await interaction.response.edit_message(embed=embed, view=self)

    async def end_battle(self, p1_win):
        """End the battle and show results"""
        self.battle_active = False
        winner = self.ctx.author if p1_win else self.target

        # Update stats and grant EXP rewards
        users = load(USERS_FILE)
        author_user = self.ensure_user(users, str(self.ctx.author.id))
        target_user = self.ensure_user(users, str(self.target.id))

        if p1_win:
            author_user["wins"] = author_user.get("wins", 0) + 1
            author_user["streak"] = author_user.get("streak", 0) + 1
            target_user["streak"] = 0
        else:
            target_user["wins"] = target_user.get("wins", 0) + 1
            target_user["streak"] = target_user.get("streak", 0) + 1
            author_user["streak"] = 0

        # Get card names for both teams
        winner_cards = [c["name"] for c in (
            self.my_team_battle if p1_win else self.en_team_battle)]
        loser_cards = [c["name"] for c in (
            self.en_team_battle if p1_win else self.my_team_battle)]

        # Grant EXP rewards using our new system
        winner_id = self.ctx.author.id if p1_win else self.target.id
        loser_id = self.target.id if p1_win else self.ctx.author.id

        rewards = self._grant_battle_rewards(
            winner_id, loser_id, winner_cards, loser_cards)

        save(USERS_FILE, users)

        # Gang EXP reward for winner, if in a gang
        try:
            gangs = load(GANGS_FILE)
            winner_id_str = str(winner.id)
            winner_gang = None
            winner_gid = None
            for gid, g in gangs.items():
                if winner_id_str in g.get("members", []):
                    winner_gid = gid
                    winner_gang = g
                    break

            gang_exp_awarded = 0
            if winner_gang is not None:
                winner_gang.setdefault("exp", 0)
                # Simple flat EXP for now; can be scaled later by team/cards
                gang_exp_awarded = random.randint(20, 50)
                winner_gang["exp"] += gang_exp_awarded
                gangs[winner_gid] = winner_gang
                save(GANGS_FILE, gangs)
        except Exception:
            gang_exp_awarded = 0

        # Result embed
        result_embed = discord.Embed(
            title=f"🏆 {winner.display_name} Wins!",
            description=(
                f"**Battle lasted {self.turn} turns**\n"
                "\n**Highlights:**\n" + "\n".join(self.log[:10])
            ),
            color=0x2ECC71 if p1_win else 0xE74C3C
        )
        result_embed.set_author(name="PvP Battle Results",
                                icon_url=winner.display_avatar.url)

        winner_user = author_user if p1_win else target_user
        result_embed.add_field(
            name="🏆 Winner Stats",
            value=f"Total Wins: `{winner_user.get('wins', 0)}`\nWin Streak: `{winner_user.get('streak', 0)}` 🔥",
            inline=True
        )

        if gang_exp_awarded:
            result_embed.add_field(
                name="👥 Gang Reward",
                value=f"Your gang gained `{gang_exp_awarded}` EXP!",
                inline=False
            )

        if p1_win:
            remaining = [c['name'] for c in self.my_team_battle if c['hp'] > 0]
            result_embed.add_field(
                name="🔵 Remaining Team",
                value=", ".join(remaining) if remaining else "None",
                inline=True
            )
        else:
            remaining = [c['name'] for c in self.en_team_battle if c['hp'] > 0]
            result_embed.add_field(
                name="🔴 Remaining Team",
                value=", ".join(remaining) if remaining else "None",
                inline=True
            )

        # Optional footer hint
        result_embed.set_footer(
            text="Battle Complete! Use `ls fight` to find another opponent.")

        await self.msg.edit(embed=result_embed, view=None)


class CardAttackButton(Button):
    """Button for selecting a card to attack"""

    def __init__(self, card_num, card_name, card_index):
        super().__init__(
            label=f"Card {card_num}: {card_name[:15]}", style=discord.ButtonStyle.primary, row=(card_num - 1) // 2)
        self.card_index = card_index
        self.card_name = card_name

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, BattleView):
            await view.process_attack(interaction, self.card_index)


class Combat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_gang_multiplier(self, uid: int) -> float:
        """Return stat multiplier based on user's gang/crew level.

        Level is derived from gang['exp'] and gang['type']:
        - gang: level = exp // 50_000
        - crew: level = exp // 150_000
        Multiplier = 1 + (level * 0.02).
        """
        try:
            gangs = load(GANGS_FILE)
        except Exception:
            return 1.0

        uid_str = str(uid)
        for _, g in gangs.items():
            if uid_str in g.get("members", []):
                exp = int(g.get("exp", 0))
                gtype = g.get("type", "gang")
                threshold = 50000 if gtype == "gang" else 150000
                level = exp // threshold if threshold > 0 else 0
                return 1.0 + (level * 0.02)

        return 1.0

    def ensure_user(self, users, uid):
        """Ensure user exists in database"""
        if uid not in users:
            users[uid] = {
                "yen": 0,
                "cards": [],
                "fragments": {},
                "unlocked": [],
                "pulls": 12,
                "chests": {},
                "tickets": {},
                "equipment": {},
                "wins": 0,
                "streak": 0,
                "last_pull_regen_ts": 0,
                "last_claim_ts": 0,
                "reset_tokens": 0,
                "team": []
            }
        return users[uid]

    def _add_card_exp(self, user, card_name, exp_amount):
        """Add experience to a card and handle leveling up"""
        cards = user.get("cards", [])
        for card in cards:
            if card.get('name') == card_name:
                current_exp = card.get('exp', 0)
                current_level = card.get('level', 1)
                new_exp = current_exp + exp_amount

                # Calculate new level (1 level per 1000 exp)
                new_level = 1 + (new_exp // 1000)

                card['exp'] = new_exp
                card['level'] = new_level

                # Recalculate stats based on new level
                base_stats = compute_stats(card)
                card['atk'] = base_stats['atk'] + (new_level - 1) * 2
                card['hp'] = base_stats['hp'] + (new_level - 1) * 5
                card['max_hp'] = card['hp']

                return new_level > current_level
        return False

    def _add_account_exp(self, user, exp_amount):
        """Add experience to user account and handle leveling up"""
        current_exp = user.get('account_exp', 0)
        current_level = user.get('account_level', 1)
        new_exp = current_exp + exp_amount

        # Calculate new level (1 level per 5000 exp)
        new_level = 1 + (new_exp // 5000)

        user['account_exp'] = new_exp
        user['account_level'] = new_level

        return new_level > current_level

    def _grant_battle_rewards(self, winner_id, loser_id, winner_cards, loser_cards):
        """Grant EXP rewards after battle"""
        users = load(USERS_FILE)

        # Winner rewards
        winner = self.ensure_user(users, str(winner_id))
        winner_account_leveled = self._add_account_exp(
            winner, random.randint(10, 20))

        card_levelups = []
        for card_name in winner_cards:
            if self._add_card_exp(winner, card_name, random.randint(10, 30)):
                card_levelups.append(card_name)

        # Loser rewards
        loser = self.ensure_user(users, str(loser_id))
        loser_account_leveled = self._add_account_exp(
            loser, random.randint(5, 10))

        for card_name in loser_cards:
            self._add_card_exp(loser, card_name, random.randint(5, 10))

        save(USERS_FILE, users)

        return {
            'winner_account_leveled': winner_account_leveled,
            'loser_account_leveled': loser_account_leveled,
            'card_levelups': card_levelups
        }

    def get_team(self, uid):
        """Build battle-ready team for a user.

        Prefers the saved team (user['team']) of card names, up to 4.
        Falls back to the first 4 owned cards if no team is set.
        """
        users = load(USERS_FILE)
        cards_db = load(CARDS_FILE)
        user = self.ensure_user(users, str(uid))
        # Ensure team key exists for older data
        user.setdefault("team", [])
        save(USERS_FILE, users)  # Save if new user was created / upgraded

        user_cards = user.get("cards", [])
        if not user_cards:
            return []

        # Helper: find first card object by name from user's owned cards
        def find_owned_card_by_name(name: str):
            for c in user_cards:
                if c.get('name') == name:
                    return c
            return None

        # Gang/crew level multiplier
        mult = self._get_gang_multiplier(uid)

        team_data = []
        team_names = user.get("team", [])

        # 1. Use saved team names if present
        if team_names:
            for name in team_names[:4]:
                owned = find_owned_card_by_name(name)
                if not owned:
                    continue
                base = next((v for v in cards_db.values() if v.get(
                    'name') == owned.get('name')), None)
                if not base:
                    continue
                stats = compute_stats(base, owned.get('level', 1), owned.get(
                    'aura', 0), owned.get('equipped_item_id'))
                atk = int(stats['attack'] * mult)
                hp = int(stats['health'] * mult)
                team_data.append({
                    "name": owned['name'],
                    "atk": atk,
                    "hp": hp,
                    "max_hp": hp
                })

        # 2. Fallback: if no valid team entries, use first 4 owned cards
        if not team_data:
            for c in user_cards[:4]:
                base = next((v for v in cards_db.values()
                            if v.get('name') == c.get('name')), None)
                if not base:
                    continue
                stats = compute_stats(base, c.get('level', 1), c.get(
                    'aura', 0), c.get('equipped_item_id'))
                atk = int(stats['attack'] * mult)
                hp = int(stats['health'] * mult)
                team_data.append({
                    "name": c['name'],
                    "atk": atk,
                    "hp": hp,
                    "max_hp": hp
                })

        return team_data

    def _fuzzy_find_owned_card_name(self, user, search_name: str):
        """Fuzzy search for an owned card name in user's collection."""
        if not search_name:
            return None
        cards = user.get("cards", [])
        owned_names = [c.get("name", "") for c in cards]
        if not owned_names:
            return None

        # Exact (case insensitive)
        lower = search_name.lower().strip()
        for n in owned_names:
            if n.lower() == lower:
                return n

        # Substring
        partial = [n for n in owned_names if lower in n.lower()]
        if len(partial) == 1:
            return partial[0]
        if len(partial) > 1:
            best = get_close_matches(search_name, partial, n=1, cutoff=0.0)
            if best:
                return best[0]

        # Fuzzy across all names
        best = get_close_matches(search_name, owned_names, n=1, cutoff=0.6)
        return best[0] if best else None

    async def start_battle(self, ctx, target: discord.Member):
        """Shared battle setup for challenge/fight commands."""
        if target.bot:
            embed = discord.Embed(
                title="❌ Cannot Challenge Bots",
                description="You can only challenge **real players**! Bots cannot fight.\n\nUse `ls raid` to fight bosses instead.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if target.id == ctx.author.id:
            embed = discord.Embed(
                title="❌ Invalid Target",
                description="You can't challenge yourself!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        users = load(USERS_FILE)
        my_team = self.get_team(ctx.author.id)
        en_team = self.get_team(target.id)
        save(USERS_FILE, users)  # Save in case new users were created

        if not my_team:
            embed = discord.Embed(
                title="❌ No Team",
                description="You have no cards in your team! Use `ls pull` to get characters.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if not en_team:
            embed = discord.Embed(
                title="❌ Opponent Has No Team",
                description=f"**{target.display_name}** has no cards to fight with!\n\nThey need to pull characters first.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Battle initialization embed with avatars
        init_embed = discord.Embed(
            title="⚔️ Battle Started!",
            description=(
                f"**{ctx.author.display_name}** is fighting **{target.display_name}**!\n\n"
                "**Your Team** 🆚 **Their Team**\n\n"
                "**Select a card button below to attack!**"
            ),
            color=0xF1C40F
        )
        # Left: attacker avatar (author)
        init_embed.set_author(name="Player vs Player Battle",
                              icon_url=ctx.author.display_avatar.url)
        # Right: defender avatar
        init_embed.set_thumbnail(url=target.display_avatar.url)

        my_team_text = "\n".join([
            f"• **{c['name']}** (Strength: {c['atk']} | Health: {c['hp']})" for c in my_team
        ])
        en_team_text = "\n".join([
            f"• **{c['name']}** (Strength: {c['atk']} | Health: {c['hp']})" for c in en_team
        ])

        init_embed.add_field(
            name=f"🔵 {ctx.author.display_name}'s Team",
            value=my_team_text,
            inline=True
        )
        init_embed.add_field(
            name=f"🔴 {target.display_name}'s Team",
            value=en_team_text,
            inline=True
        )
        init_embed.set_footer(
            text="Click a card button to attack with that card!")

        # Create battle view with buttons
        view = BattleView(ctx, my_team, en_team, target, self.ensure_user)
        msg = await ctx.send(embed=init_embed, view=view)
        view.msg = msg

    @commands.command(name="challenge", aliases=["chall", "duel"])
    async def challenge(self, ctx, target: discord.Member = None):
        """Challenge another specific player to a battle. Usage: ls challenge @user"""
        if not target:
            embed = discord.Embed(
                title="❌ Invalid Target",
                description="Please mention a **real player** to challenge!\nUsage: `ls challenge @user`",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        await self.start_battle(ctx, target)

    @commands.command(name="fight")
    async def fight(self, ctx):
        """Find a random player and start a fight. Usage: ls fight"""
        guild = ctx.guild
        if guild is None:
            embed = discord.Embed(
                title="❌ Guild Only",
                description="You can only use `ls fight` inside a server.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        users = load(USERS_FILE)
        candidate_members = []
        for uid_str in users.keys():
            try:
                uid = int(uid_str)
            except ValueError:
                continue
            if uid == ctx.author.id:
                continue
            member = guild.get_member(uid)
            if not member or member.bot:
                continue
            if self.get_team(uid):
                candidate_members.append(member)

        if not candidate_members:
            embed = discord.Embed(
                title="❌ No Opponents Found",
                description="No suitable opponents found. Other players must have at least one card to fight.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        target = random.choice(candidate_members)
        await self.start_battle(ctx, target)

    @commands.command(name="team", aliases=["teamview", "myteam"])
    async def team_view(self, ctx):
        """View your active team. Usage: ls team"""
        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        user.setdefault("team", [])
        cards = user.get("cards", [])

        if not cards:
            embed = discord.Embed(
                title="📦 No Cards",
                description="You don't own any cards yet! Use `ls pull` to get characters.",
                color=0x95A5A6
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        team_names = user.get("team", [])[:4]
        if not team_names:
            desc = "You have no active team set. The first 4 cards you own will be used by default in battles.\n\nUse `ls teamadd <card name>` to add cards to your team (max 4)."
        else:
            lines = [f"• **{name}**" for name in team_names]
            desc = "\n".join(lines)

        embed = discord.Embed(
            title=f"🃏 {ctx.author.display_name}'s Team",
            description=desc,
            color=0x5865F2
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="teamadd")
    async def team_add(self, ctx, *, card_name: str = None):
        """Add a card to your active team (max 4). Usage: ls teamadd <card name>"""
        if not card_name:
            return await ctx.send("❌ Usage: `ls teamadd <card name>`")

        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        user.setdefault("team", [])

        if len(user["team"]) >= 4:
            return await ctx.send("❌ Your team is already full (max 4 cards). Use `ls teamremove` to free a slot.")

        owned_name = self._fuzzy_find_owned_card_name(user, card_name)
        if not owned_name:
            return await ctx.send(f"❌ You don't own any card matching: **{card_name}**")

        if owned_name in user["team"]:
            return await ctx.send(f"❌ **{owned_name}** is already in your team.")

        user["team"].append(owned_name)
        save(USERS_FILE, users)

        embed = discord.Embed(
            title="✅ Team Updated",
            description=f"**{owned_name}** has been added to your team.",
            color=0x2ECC71
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="teamremove")
    async def team_remove(self, ctx, *, card_name: str = None):
        """Remove a card from your active team. Usage: ls teamremove <card name>"""
        if not card_name:
            return await ctx.send("❌ Usage: `ls teamremove <card name>` or `ls teamremoveall`")

        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        user.setdefault("team", [])

        if not user["team"]:
            return await ctx.send("❌ You have no cards in your team.")

        owned_name = self._fuzzy_find_owned_card_name(user, card_name)
        if not owned_name or owned_name not in user["team"]:
            return await ctx.send(f"❌ **{card_name}** is not in your current team.")

        user["team"] = [n for n in user["team"] if n != owned_name]
        save(USERS_FILE, users)

        embed = discord.Embed(
            title="✅ Team Updated",
            description=f"**{owned_name}** has been removed from your team.",
            color=0xE67E22
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="teamremoveall", aliases=["teamclear"])
    async def team_remove_all(self, ctx):
        """Remove all cards from your active team. Usage: ls teamremoveall"""
        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        user.setdefault("team", [])

        if not user["team"]:
            return await ctx.send("ℹ️ Your team is already empty. Battles will use your first 4 cards by default.")

        user["team"] = []
        save(USERS_FILE, users)

        embed = discord.Embed(
            title="✅ Team Cleared",
            description="Your active team has been cleared. Battles will now use your first 4 owned cards by default.",
            color=0xE74C3C
        )
        return await ctx.send(embed=embed)

    @commands.command(name="fight")
    async def fight(self, ctx):
        """Find a random player and start a fight. Usage: ls fight"""
        guild = ctx.guild
        if guild is None:
            embed = discord.Embed(
                title="❌ Guild Only",
                description="You can only use `ls fight` inside a server.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        users = load(USERS_FILE)
        candidate_members = []
        for uid_str in users.keys():
            try:
                uid = int(uid_str)
            except ValueError:
                continue
            if uid == ctx.author.id:
                continue
            member = guild.get_member(uid)
            if not member or member.bot:
                continue
            if self.get_team(uid):
                candidate_members.append(member)

        if not candidate_members:
            embed = discord.Embed(
                title="❌ No Opponents Found",
                description="No suitable opponents found. Other players must have at least one card to fight.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

    @commands.command(name="teamadd")
    async def team_add(self, ctx, *, card_name: str = None):
        """Add a card to your active team (max 4). Usage: ls teamadd <card name>"""
        if not card_name:
            return await ctx.send("❌ Usage: `ls teamadd <card name>`")

        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        user.setdefault("team", [])

        if len(user["team"]) >= 4:
            return await ctx.send("❌ Your team is already full (max 4 cards). Use `ls teamremove` to free a slot.")

        owned_name = self._fuzzy_find_owned_card_name(user, card_name)
        if not owned_name:
            return await ctx.send(f"❌ You don't own any card matching: **{card_name}**")

        if owned_name in user["team"]:
            return await ctx.send(f"❌ **{owned_name}** is already in your team.")

        user["team"].append(owned_name)
        save(USERS_FILE, users)

        embed = discord.Embed(
            title="✅ Team Updated",
            description=f"**{owned_name}** has been added to your team.",
            color=0x2ECC71
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="teamremove")
    async def team_remove(self, ctx, *, card_name: str = None):
        """Remove a card from your active team. Usage: ls teamremove <card name>"""
        if not card_name:
            return await ctx.send("❌ Usage: `ls teamremove <card name>` or `ls teamremoveall`")

        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        user.setdefault("team", [])

        if not user["team"]:
            return await ctx.send("❌ You have no cards in your team.")

        owned_name = self._fuzzy_find_owned_card_name(user, card_name)
        if not owned_name or owned_name not in user["team"]:
            return await ctx.send(f"❌ **{card_name}** is not in your current team.")

        user["team"] = [n for n in user["team"] if n != owned_name]
        save(USERS_FILE, users)

        embed = discord.Embed(
            title="✅ Team Updated",
            description=f"**{owned_name}** has been removed from your team.",
            color=0xE67E22
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="teamremoveall", aliases=["teamclear"])
    async def team_remove_all(self, ctx):
        """Remove all cards from your active team. Usage: ls teamremoveall"""
        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        user.setdefault("team", [])

        if not user["team"]:
            return await ctx.send("ℹ️ Your team is already empty. Battles will use your first 4 cards by default.")

        user["team"] = []
        save(USERS_FILE, users)

        embed = discord.Embed(
            title="✅ Team Cleared",
            description="Your active team has been cleared. Battles will now use your first 4 owned cards by default.",
            color=0xE74C3C
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.group(name="brt", aliases=["boss_raid_team"])
    async def boss_raid_team(self, ctx):
        """Boss raid team management. Usage: ls brt <subcommand>"""
        if ctx.invoked_subcommand is None:
            # Show the team by default
            users = load(USERS_FILE)
            user = self.ensure_user(users, str(ctx.author.id))
            user.setdefault("boss_raid_team", [])
            cards = user.get("cards", [])

            if not cards:
                embed = discord.Embed(
                    title="📦 No Cards",
                    description="You don't own any cards yet! Use `ls pull` to get characters.",
                    color=0x95A5A6
                )
                embed.set_author(name=ctx.author.display_name,
                                 icon_url=ctx.author.display_avatar.url)
                return await ctx.send(embed=embed)

            team_names = user.get("boss_raid_team", [])
            if not team_names:
                desc = "You have no boss raid team set. Use `ls brt add <card name>` to add cards to your boss raid team (max 2)."
            else:
                lines = [f"• **{name}**" for name in team_names]
                desc = "\n".join(lines)

            embed = discord.Embed(
                title=f"🐉 {ctx.author.display_name}'s Boss Raid Team",
                description=desc,
                color=0x8B0000
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            embed.set_footer(text="Use: ls brt add/remove/view")
            await ctx.send(embed=embed)

    @boss_raid_team.command(name="add")
    async def brt_add(self, ctx, *, card_name: str = None):
        """Add a card to your boss raid team (max 2). Usage: ls brt add <card name>"""
        if not card_name:
            return await ctx.send("❌ Usage: `ls brt add <card name>`")

        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        user.setdefault("boss_raid_team", [])

        print(f"DEBUG: Trying to add card: {card_name}")
        print(
            f"DEBUG: User cards: {[card.get('name', 'Unknown') for card in user.get('cards', [])[:5]]}")

        if len(user["boss_raid_team"]) >= 2:
            return await ctx.send("❌ Your boss raid team is already full (max 2 cards). Use `ls brt remove` to free a slot.")

        owned_name = self._fuzzy_find_owned_card_name(user, card_name)
        print(f"DEBUG: Found owned card: {owned_name}")

        if not owned_name:
            return await ctx.send(f"❌ You don't own any card matching: **{card_name}**")

        if owned_name in user["boss_raid_team"]:
            return await ctx.send(f"❌ **{owned_name}** is already in your boss raid team.")

        user["boss_raid_team"].append(owned_name)
        save(USERS_FILE, users)
        print(f"DEBUG: Added {owned_name} to boss raid team")

        embed = discord.Embed(
            title="✅ Boss Raid Team Updated",
            description=f"**{owned_name}** has been added to your boss raid team.",
            color=0x2ECC71
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @boss_raid_team.command(name="remove")
    async def brt_remove(self, ctx, *, card_name: str = None):
        """Remove a card from your boss raid team. Usage: ls brt remove <card name>"""
        if not card_name:
            return await ctx.send("❌ Usage: `ls brt remove <card name>`")

        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        user.setdefault("boss_raid_team", [])

        if not user["boss_raid_team"]:
            return await ctx.send("❌ You have no cards in your boss raid team.")

        owned_name = self._fuzzy_find_owned_card_name(user, card_name)
        if not owned_name or owned_name not in user["boss_raid_team"]:
            return await ctx.send(f"❌ **{card_name}** is not in your current boss raid team.")

        user["boss_raid_team"] = [
            n for n in user["boss_raid_team"] if n != owned_name]
        save(USERS_FILE, users)

        embed = discord.Embed(
            title="✅ Boss Raid Team Updated",
            description=f"**{owned_name}** has been removed from your boss raid team.",
            color=0xE67E22
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @boss_raid_team.command(name="view")
    async def brt_view(self, ctx):
        """View your boss raid team. Usage: ls brt view"""
        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        user.setdefault("boss_raid_team", [])
        cards = user.get("cards", [])

        if not cards:
            embed = discord.Embed(
                title="📦 No Cards",
                description="You don't own any cards yet! Use `ls pull` to get characters.",
                color=0x95A5A6
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        team_names = user.get("boss_raid_team", [])
        if not team_names:
            desc = "You have no boss raid team set. Use `ls brt add <card name>` to add cards to your boss raid team (max 2)."
        else:
            lines = [f"• **{name}**" for name in team_names]
            desc = "\n".join(lines)

        embed = discord.Embed(
            title=f"🐉 {ctx.author.display_name}'s Boss Raid Team",
            description=desc,
            color=0x8B0000
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    def _fuzzy_find_owned_card_name(self, user, search_name):
        """Find owned card by name with fuzzy matching"""
        cards = user.get("cards", [])
        card_names = [card.get('name', '') for card in cards]

        search_lower = search_name.lower()

        # Exact match first
        for name in card_names:
            if name.lower() == search_lower:
                return name

        # Partial match
        matches = [name for name in card_names if search_lower in name.lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # Use difflib for fuzzy matching
            from difflib import get_close_matches
            best = get_close_matches(search_name, matches, n=1, cutoff=0.6)
            return best[0] if best else None

        return None

    @commands.command(name="bossraid")
    async def raid(self, ctx, *, boss_name: str = None):
        """Start a boss raid using a specific ticket. Usage: ls bossraid <boss_name>"""
        print(f"DEBUG: Received boss_name: '{boss_name}'")

        if not boss_name:
            return await ctx.send("❌ Usage: `ls bossraid <boss_name>`\nExample: `ls bossraid Zack Lee`\n\nAvailable bosses: Zack Lee, Vasco, Eli Jang, Jake Kim, OG Daniel, Johan Seong, Jinyeong Park, Daniel Park (SB), James Lee, Goo Kim, Shingen Yamazaki, Gapryong Kim, Gun Park")

        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))

        # Load boss data
        try:
            bosses = load(BOSS_FILE)
        except Exception:
            return await ctx.send("❌ Could not load boss data!")

        # Check if boss exists
        boss_key = None

        # Try exact key match first
        if boss_name in bosses:
            boss_key = boss_name
        else:
            # Try exact name match
            for key, data in bosses.items():
                if data['name'].lower() == boss_name.lower():
                    boss_key = key
                    break

            # If still not found, try fuzzy matching
            if not boss_key:
                available_names = [bosses[key]['name']
                                   for key in bosses.keys()]
                from difflib import get_close_matches
                name_close_matches = get_close_matches(
                    boss_name, available_names, n=1, cutoff=0.6)
                if name_close_matches:
                    # Find the key for this name
                    for key, name in zip(bosses.keys(), available_names):
                        if name == name_close_matches[0]:
                            boss_key = key
                            break
                else:
                    embed = discord.Embed(
                        title="❌ Boss Not Found",
                        description=f"Boss '**{boss_name}**' not found!\n\nAvailable bosses: {', '.join(available_names)}",
                        color=0xE74C3C
                    )
                    return await ctx.send(embed=embed)

        if not boss_key:
            embed = discord.Embed(
                title="❌ Boss Not Found",
                description=f"Boss '**{boss_name}**' not found!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        boss_data = bosses[boss_key]

        # Check if user has the ticket
        tickets = user.get("tickets", {})
        print(f"DEBUG: Looking for boss: {boss_data['name']}")
        print(f"DEBUG: User tickets: {list(tickets.keys())}")

        # Check multiple ticket formats
        boss_tickets = 0
        ticket_key = None

        # Try different ticket key formats
        possible_keys = [
            boss_key,                    # "Zack Lee"
            boss_data['name'],          # "Zack Lee"
            f"{boss_key.lower()}_ticket",      # "zack lee_ticket"
            # "zack_lee_ticket"
            f"{boss_key.replace(' ', '_').lower()}_ticket",
            # "zack_lee_ticket"
            f"{boss_data['name'].lower().replace(' ', '_')}_ticket"
        ]

        print(f"DEBUG: Trying ticket keys: {possible_keys}")

        for key in possible_keys:
            if key in tickets and tickets[key] > 0:
                boss_tickets = tickets[key]
                ticket_key = key
                print(f"DEBUG: Found {boss_tickets} tickets with key: {key}")
                break

        print(f"DEBUG: Final ticket count: {boss_tickets}")

        if boss_tickets <= 0:
            # Check if user has any tickets at all for better error message
            if tickets:
                ticket_list = ", ".join(
                    [key.replace('_ticket', ' ticket') for key in list(tickets.keys())[:5]])
                embed = discord.Embed(
                    title="❌ No Ticket",
                    description=f"You don't have any **{boss_data['name']}** tickets!\n**Your tickets:** {ticket_list}\n\nGet tickets from drops or other rewards.",
                    color=0xE74C3C
                )
            else:
                embed = discord.Embed(
                    title="❌ No Tickets",
                    description=f"You don't have any boss raid tickets!\nGet tickets from drops or other rewards.\n\n**Available bosses:** Zack Lee, Vasco, Eli Jang, Jake Kim, OG Daniel, Johan Seong, Jinyeong Park, Daniel Park (SB), James Lee, Goo Kim, Shingen Yamazaki, Gapryong Kim, Gun Park",
                    color=0xE74C3C
                )
            return await ctx.send(embed=embed)

        # Check if user has boss raid team
        boss_raid_team = user.get("boss_raid_team", [])
        if not boss_raid_team:
            embed = discord.Embed(
                title="❌ No Boss Raid Team",
                description="You need to set up a boss raid team first! Use `ls brt add <card name>` to add cards (max 2).",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Get user's boss raid team cards
        team_cards = []
        for card_name in boss_raid_team:
            card = next((c for c in user.get("cards", [])
                        if c.get('name') == card_name), None)
            if card:
                team_cards.append(card)

        if not team_cards:
            embed = discord.Embed(
                title="❌ Invalid Boss Raid Team",
                description="Your boss raid team contains invalid cards. Please set up your team again.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Create the ticket view
        view = BossTicketView(ctx, boss_key, boss_data, ctx.author, team_cards)

        # Create embed with boss info
        embed = discord.Embed(
            title=f"🐉 {boss_data['name']} Boss Raid",
            description=f"A powerful **{boss_data['name']}** appears!\n\n**Max Players:** `{boss_data['max_players']}`\n**Ticket Cost:** 1 {boss_data['name']} ticket",
            color=0xDC143C
        )

        if boss_data.get('image'):
            # Convert Tenor URL to proper format for Discord
            image_url = boss_data['image']
            print(f"DEBUG: Original boss image URL: {image_url}")

            if 'tenor.com' in image_url:
                # Try multiple Tenor formats
                possible_urls = [
                    image_url + '.gif',  # Add .gif extension
                    image_url.replace(
                        # Tenor format
                        'view/', 'view/').replace('.gif', '-gif.gif'),
                    image_url + '-gif.gif',  # Another Tenor format
                    image_url  # Original as fallback
                ]

                for url in possible_urls:
                    try:
                        embed.set_image(url=url)
                        print(f"DEBUG: Successfully set image with URL: {url}")
                        break
                    except Exception as e:
                        print(f"DEBUG: Failed with URL {url}: {e}")
                        continue
            else:
                # Non-Tenor URLs, use as-is
                try:
                    embed.set_image(url=image_url)
                    print("DEBUG: Non-Tenor image set successfully")
                except Exception as e:
                    print(f"DEBUG: Failed to set non-Tenor image: {e}")

        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Host: Click START | Others: Click JOIN")

        # Add boss stats as separate fields
        embed.add_field(
            name="⚔️ Boss Stats",
            value=f"**ATK:** `{boss_data['stats']['attack']}`\n**HP:** `{boss_data['stats']['health']}`\n**SPD:** `{boss_data['stats']['speed']}`",
            inline=False
        )

        # Show host's team
        team_info = []
        for card in team_cards:
            hp_percent = (card['hp'] / card['max_hp']) * 100
            team_info.append(
                f"**{card['name']}**: `{card['hp']}`/`{card['max_hp']}` ({hp_percent:.1f}%)")

        embed.add_field(
            name=f"🃏 {ctx.author.display_name}'s Team",
            value="\n".join(team_info),
            inline=False
        )

        embed.add_field(
            name="🎫 Tickets Remaining",
            value=f"`{boss_tickets - 1}` {boss_data['name']} tickets",
            inline=False
        )

        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @commands.command(name="kill")
    async def kill_command(self, ctx, killer: str = None, victim: str = None, amount: str = None):
        """Kill fragments to gain aura points. Usage: ls kill <killer> <victim> <number/all>"""
        print(
            f"DEBUG: Kill command called with killer={killer}, victim={victim}, amount={amount}")
        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        fragments = user.get("fragments", {})
        print(f"DEBUG: User fragments: {fragments}")

        if not fragments or all(count == 0 for count in fragments.values()):
            embed = discord.Embed(
                title="❌ No Fragments",
                description="You don't have any fragments to kill! Get fragments by pulling duplicate characters.",
                color=0xE74C3C
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        # Validate parameters
        if not killer or not victim or not amount:
            embed = discord.Embed(
                title="❌ Invalid Usage",
                description="Usage: `ls kill <killer> <victim> <number/all>`",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Find killer fragment
        killer_fragment = self._find_fragment(fragments, killer)
        print(f"DEBUG: Killer fragment found: {killer_fragment}")
        if not killer_fragment:
            embed = discord.Embed(
                title="❌ Killer Fragment Not Found",
                description=f"You don't have any fragment matching: **{killer}**",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Find victim fragment
        victim_fragment = self._find_fragment(fragments, victim)
        print(f"DEBUG: Victim fragment found: {victim_fragment}")
        if not victim_fragment:
            embed = discord.Embed(
                title="❌ Victim Fragment Not Found",
                description=f"You don't have any fragment matching: **{victim}**",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Handle amount parameter
        if amount.lower() == "all":
            # Kill all victim fragments
            victim_count = fragments.get(victim_fragment, 0)
            if victim_count == 0:
                embed = discord.Embed(
                    title="❌ No Victim Fragments",
                    description=f"You have no **{victim_fragment}** fragments to kill.",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)
            amount_to_kill = victim_count
        else:
            # Parse number
            try:
                amount_to_kill = int(amount)
                if amount_to_kill <= 0:
                    return await ctx.send("❌ Amount must be greater than 0!")
            except ValueError:
                embed = discord.Embed(
                    title="❌ Invalid Amount",
                    description="Amount must be a positive number or 'all'.",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

        # Check if user has enough victim fragments
            victim_count = fragments.get(victim_fragment, 0)
            if victim_count < amount_to_kill:
                embed = discord.Embed(
                    title="❌ Not Enough Victim Fragments",
                    description=f"You need `{amount_to_kill}` **{victim_fragment}** fragments but only have `{victim_count}`",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            # Get victim card data to determine rarity
            cards_db = load(CARDS_FILE)
            victim_base = next((c for c in cards_db.values()
                               if c.get('name') == victim_fragment), None)
            if not victim_base:
                return await ctx.send("❌ Could not find victim card data!")

            # Get aura drop value based on rarity
            rarities = load(RARITIES_FILE)
            rarity = victim_base.get('rarity', 'C')
            rarity_info = rarities.get(rarity, {})
            aura_per_kill = rarity_info.get('aura_drop', 5)

            # Calculate total aura gained
            total_aura = aura_per_kill * amount_to_kill

            # Remove victim fragments
            fragments[victim_fragment] = victim_count - amount_to_kill
            if fragments[victim_fragment] <= 0:
                del fragments[victim_fragment]

            # Add aura to killer card (find card in user's cards)
            cards = user.get("cards", [])
            killer_card_found = False
            for card in cards:
                if card.get('name') == killer_fragment:
                    card['aura'] = card.get('aura', 0) + total_aura
                    killer_card_found = True
                    break

            if not killer_card_found:
                # If killer card not owned, add aura to user's account
                user.setdefault('aura_balance', 0)
                user['aura_balance'] += total_aura

            user['fragments'] = fragments
            save(USERS_FILE, users)

            # Create result embed
            embed = discord.Embed(
                title="⚔️ Fragments Killed Successfully!",
                description=(
                    f"**{killer_fragment}** killed `{amount_to_kill}` **{victim_fragment}** fragments!\n\n"
                    f"**Aura Gained:** `{total_aura}` points\n"
                    f"**Rate:** `{aura_per_kill}` aura per kill"
                ),
                color=0x2ECC71
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)

            if killer_card_found:
                embed.add_field(
                    name="📊 Killer Card Status",
                    value=f"**{killer_fragment}** now has `{sum(c.get('aura', 0) for c in cards if c.get('name') == killer_fragment)}` total aura points",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📊 Aura Balance",
                    value=f"Your aura balance is now `{user.get('aura_balance', 0)}` points",
                    inline=False
                )

            embed.add_field(
                name="🎯 Fragments Removed",
                value=f"Removed `{amount_to_kill}` **{victim_fragment}** fragments (remaining: `{fragments.get(victim_fragment, 0)}`)",
                inline=False
            )

            await ctx.send(embed=embed)

    def _find_fragment(self, fragments, search_name):
        """Find fragment by name with fuzzy matching"""
        search_lower = search_name.lower()

        # Exact match first
        for name in fragments.keys():
            if name.lower() == search_lower and fragments[name] > 0:
                return name

        # Partial match
        matches = [name for name in fragments.keys()
                   if search_lower in name.lower() and fragments[name] > 0]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # Use difflib for fuzzy matching
            from difflib import get_close_matches
            best = get_close_matches(search_name, matches, n=1, cutoff=0.6)
            return best[0] if best else None

        return None


class BossTicketView(View):
    """Interactive boss ticket view with join/start functionality"""

    def __init__(self, ctx, boss_key, boss_data, host, host_team):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.boss_key = boss_key
        self.boss_data = boss_data
        self.host = host
        self.host_team = host_team
        self.joined_players = []  # List of (player, team) tuples
        self.raid_started = False

    @button(label="🚀 START RAID", style=discord.ButtonStyle.success, custom_id="start")
    async def start_button(self, interaction: discord.Interaction, button: Button):
        """Start the boss raid (host only)"""
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("❌ Only the host can start the raid!", ephemeral=True)
            return

        if self.raid_started:
            await interaction.response.send_message("❌ Raid has already started!", ephemeral=True)
            return

        # Consume the host's ticket
        users = load(USERS_FILE)
        user = self.ensure_user(users, str(self.host.id))
        tickets = user.get("tickets", {})

        # Try to consume ticket using multiple formats
        ticket_key = None
        possible_keys = [
            self.boss_key,                    # "Zack Lee"
            self.boss_data['name'],          # "Zack Lee"
            f"{self.boss_key.lower()}_ticket",      # "zack lee_ticket"
            # "zack_lee_ticket"
            f"{self.boss_key.replace(' ', '_').lower()}_ticket",
            # "zack_lee_ticket"
            f"{self.boss_data['name'].lower().replace(' ', '_')}_ticket"
        ]

        for key in possible_keys:
            if key in tickets and tickets[key] > 0:
                ticket_key = key
                break

        if ticket_key:
            tickets[ticket_key] = tickets[ticket_key] - 1
            if tickets[ticket_key] <= 0:
                del tickets[ticket_key]
            user["tickets"] = tickets
            save(USERS_FILE, users)
            print(f"DEBUG: Consumed 1 {ticket_key} ticket")
        else:
            print(f"DEBUG: No ticket found to consume!")
            await interaction.response.send_message("❌ Ticket not found!", ephemeral=True)
            return

        self.raid_started = True

        # Prepare all players
        all_players = [(self.host, self.host_team)] + self.joined_players

        # Create the boss raid view
        boss_stats = self.boss_data['stats']
        boss = {
            'name': self.boss_data['name'],
            'atk': boss_stats['attack'],
            'hp': boss_stats['health'],
            'speed': boss_stats['speed'],
            'max_players': self.boss_data['max_players']
        }

        raid_view = BossRaidView(self.ctx, boss, all_players)

        # Update embed to show raid started
        embed = discord.Embed(
            title=f"🐉 {self.boss_data['name']} Raid Started!",
            description=f"The battle against **{self.boss_data['name']}** begins!",
            color=0x2ECC71
        )

        if self.boss_data.get('image'):
            # Convert Tenor URL to proper format for Discord
            image_url = self.boss_data['image']
            if 'tenor.com' in image_url:
                if not image_url.endswith('.gif'):
                    # Convert Tenor view URL to direct GIF URL
                    image_url = image_url + '.gif'
                # Ensure proper Tenor format
                if '-gif' not in image_url:
                    image_url = image_url.replace('.gif', '-gif.gif')
            try:
                embed.set_image(url=image_url)
            except Exception:
                # Fallback: try without modifications if the URL format fails
                try:
                    embed.set_image(url=self.boss_data['image'])
                except Exception:
                    # If all fails, don't set image (embed will work without it)
                    pass

        embed.set_author(name=self.host.display_name,
                         icon_url=self.host.display_avatar.url)
        embed.set_footer(text="Raid in progress...")

        # Add boss stats as separate field
        embed.add_field(
            name="⚔️ Boss Stats",
            value=f"**ATK:** `{boss['atk']}`\n**HP:** `{boss['hp']}`\n**SPD:** `{boss['speed']}`",
            inline=False
        )

        # Show all players' teams
        for player, team in all_players:
            team_info = []
            for card in team:
                hp_percent = (card['hp'] / card['max_hp']) * 100
                team_info.append(
                    f"**{card['name']}**: `{card['hp']}`/`{card['max_hp']}` ({hp_percent:.1f}%)")

            embed.add_field(
                name=f"🃏 {player.display_name}'s Team",
                value="\n".join(team_info),
                inline=False
            )

        # Disable all buttons
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

        # Send the raid view
        raid_embed = discord.Embed(
            title=f"⚔️ {self.boss_data['name']} Battle",
            description="Choose your actions below!",
            color=0xDC143C
        )
        raid_embed.set_author(name=self.host.display_name,
                              icon_url=self.host.display_avatar.url)

        raid_message = await self.ctx.send(embed=raid_embed, view=raid_view)
        raid_view.ctx.message = raid_message

    @button(label="👥 JOIN RAID", style=discord.ButtonStyle.primary, custom_id="join")
    async def join_button(self, interaction: discord.Interaction, button: Button):
        """Join the boss raid"""
        if self.raid_started:
            await interaction.response.send_message("❌ Raid has already started!", ephemeral=True)
            return

        if interaction.user.id == self.host.id:
            await interaction.response.send_message("❌ You're the host! Use START RAID to begin.", ephemeral=True)
            return

        # Check if already joined
        for player, _ in self.joined_players:
            if player.id == interaction.user.id:
                await interaction.response.send_message("❌ You've already joined this raid!", ephemeral=True)
                return

        # Check max players
        total_players = 1 + len(self.joined_players)  # Host + joined players
        if total_players >= self.boss_data['max_players']:
            await interaction.response.send_message(f"❌ Raid is full! Max players: {self.boss_data['max_players']}", ephemeral=True)
            return

        # Check if user has boss raid team
        users = load(USERS_FILE)
        user = self.ensure_user(users, str(interaction.user.id))
        boss_raid_team = user.get("boss_raid_team", [])

        if not boss_raid_team:
            await interaction.response.send_message("❌ You need a boss raid team! Use `ls brt add <card>` to set one up.", ephemeral=True)
            return

        # Get user's boss raid team cards
        team_cards = []
        for card_name in boss_raid_team:
            card = next((c for c in user.get("cards", [])
                        if c.get('name') == card_name), None)
            if card:
                team_cards.append(card)

        if not team_cards:
            await interaction.response.send_message("❌ Your boss raid team has invalid cards!", ephemeral=True)
            return

        # Add to joined players
        self.joined_players.append((interaction.user, team_cards))

        # Update embed
        await self.update_embed(interaction)

        await interaction.response.send_message(f"✅ You joined the **{self.boss_data['name']}** raid!", ephemeral=True)

    async def update_embed(self, interaction):
        """Update the embed to show current players"""
        embed = discord.Embed(
            title=f"🐉 {self.boss_data['name']} Boss Raid",
            description=f"A powerful **{self.boss_data['name']}** appears!\n\n**Players:** {1 + len(self.joined_players)}/{self.boss_data['max_players']}\n**Ticket Cost:** 1 {self.boss_data['name']} ticket",
            color=0xDC143C
        )

        if self.boss_data.get('image'):
            # Convert Tenor URL to proper format for Discord
            image_url = self.boss_data['image']
            if 'tenor.com' in image_url:
                if not image_url.endswith('.gif'):
                    # Convert Tenor view URL to direct GIF URL
                    image_url = image_url + '.gif'
                # Ensure proper Tenor format
                if '-gif' not in image_url:
                    image_url = image_url.replace('.gif', '-gif.gif')
            try:
                embed.set_image(url=image_url)
            except Exception:
                # Fallback: try without modifications if the URL format fails
                try:
                    embed.set_image(url=self.boss_data['image'])
                except Exception:
                    # If all fails, don't set image (embed will work without it)
                    pass

        embed.set_author(name=self.host.display_name,
                         icon_url=self.host.display_avatar.url)
        embed.set_footer(text="Host: Click START | Others: Click JOIN")

        # Add boss stats as separate fields
        embed.add_field(
            name="⚔️ Boss Stats",
            value=f"**ATK:** `{self.boss_data['stats']['attack']}`\n**HP:** `{self.boss_data['stats']['health']}`\n**SPD:** `{self.boss_data['stats']['speed']}`",
            inline=False
        )

        # Show host's team
        team_info = []
        for card in self.host_team:
            hp_percent = (card['hp'] / card['max_hp']) * 100
            team_info.append(
                f"**{card['name']}**: `{card['hp']}`/`{card['max_hp']}` ({hp_percent:.1f}%)")

        embed.add_field(
            name=f"🃏 {self.host.display_name}'s Team (Host)",
            value="\n".join(team_info),
            inline=False
        )

        # Show joined players' teams
        for player, team in self.joined_players:
            team_info = []
            for card in team:
                hp_percent = (card['hp'] / card['max_hp']) * 100
                team_info.append(
                    f"**{card['name']}**: `{card['hp']}`/`{card['max_hp']}` ({hp_percent:.1f}%)")

            embed.add_field(
                name=f"🃏 {player.display_name}'s Team",
                value="\n".join(team_info),
                inline=False
            )

        # Update join button if full
        total_players = 1 + len(self.joined_players)
        if total_players >= self.boss_data['max_players']:
            for child in self.children:
                if child.custom_id == "join":
                    child.disabled = True
                    child.label = "🔒 RAID FULL"

        await interaction.message.edit(embed=embed, view=self)


class BossRaidView(View):
    """Interactive boss raid view with action buttons"""

    def __init__(self, ctx, boss, all_players):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.boss = boss
        self.all_players = all_players  # List of (player, cards) tuples
        self.boss_hp = boss['hp']
        self.boss_max_hp = boss['hp']
        self.turn = 0
        self.max_turns = 20
        self.player_teams_battle = []
        self.log = []
        self.raid_active = True
        self.player_turns = {}  # Track which player's turn it is

        # Initialize battle data for each player
        for player, cards in all_players:
            self.player_teams_battle.append({
                'player': player,
                'cards': [{"name": c["name"], "atk": c["atk"], "hp": c["hp"], "max_hp": c["max_hp"]} for c in cards]
            })
            # All players can act initially
            self.player_turns[player.id] = True

    def get_player_cards(self, player_id):
        """Get a player's cards in battle"""
        for team_data in self.player_teams_battle:
            if team_data['player'].id == player_id:
                return team_data['cards']
        return []

    def get_alive_cards(self, player_id):
        """Get a player's alive cards"""
        cards = self.get_player_cards(player_id)
        return [c for c in cards if c['hp'] > 0]

    def create_card_button(self, card, player):
        """Create a button for a specific card"""
        label = f"⚔️ {card['name']}"
        custom_id = f"card_{player.id}_{card['name']}"

        # Disable button if card is dead or player already acted
        disabled = card['hp'] <= 0 or not self.player_turns.get(
            player.id, False)

        return Button(label=label, style=discord.ButtonStyle.primary, custom_id=custom_id, disabled=disabled, row=0)

    def update_view_buttons(self):
        """Update view buttons to show only current player's cards"""
        self.clear_items()

        # Find current player (first player who hasn't acted)
        current_player = None
        for player, _ in self.all_players:
            if self.player_turns.get(player.id, False):
                current_player = player
                break

        if not current_player:
            return  # No valid player turn

        # Add buttons for current player's alive cards
        alive_cards = self.get_alive_cards(current_player.id)
        for card in alive_cards[:3]:  # Max 3 buttons per row
            button = self.create_card_button(card, current_player)
            self.add_item(button)

        # Add action buttons
        self.add_item(Button(
            label="🛡️ Defend", style=discord.ButtonStyle.secondary, custom_id="defend", row=1))
        self.add_item(Button(
            label="💚 Heal", style=discord.ButtonStyle.success, custom_id="heal", row=1))
        self.add_item(Button(label="⏭️ End Turn",
                      style=discord.ButtonStyle.danger, custom_id="end_turn", row=2))

    async def callback(self, interaction: discord.Interaction):
        """Handle button interactions"""
        await self.handle_button_click(interaction)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the current player to interact"""
        current_player = None
        for player, _ in self.all_players:
            if self.player_turns.get(player.id, False):
                current_player = player
                break

        if current_player and interaction.user.id == current_player.id:
            return True

        await interaction.response.send_message("It's not your turn!", ephemeral=True)
        return False

    async def handle_card_attack(self, interaction: discord.Interaction, player, card_name):
        """Handle card attack"""
        if not self.raid_active:
            await interaction.response.send_message("The raid has ended!", ephemeral=True)
            return

        player_cards = self.get_alive_cards(player.id)
        attacker = next(
            (c for c in player_cards if c['name'] == card_name), None)

        if not attacker:
            await interaction.response.send_message("Card not found or defeated!", ephemeral=True)
            return

        # Attack boss
        dmg = int(attacker['atk'] * (0.8 + random.random() * 0.4))
        self.boss_hp = max(0, self.boss_hp - dmg)

        self.log.append(
            f"⚔️ **{player.display_name}'s {attacker['name']}** deals `{dmg}` damage to **{self.boss['name']}**!")

        # Boss counter-attacks random player
        if self.boss_hp > 0:
            all_alive_cards = []
            for team_data in self.player_teams_battle:
                for card in team_data['cards']:
                    if card['hp'] > 0:
                        all_alive_cards.append((team_data['player'], card))

            if all_alive_cards:
                target_player, target_card = random.choice(all_alive_cards)
                boss_dmg = int(self.boss['atk'] *
                               (0.9 + random.random() * 0.3))
                target_card['hp'] = max(0, target_card['hp'] - boss_dmg)
                self.log.append(
                    f"💀 **{self.boss['name']}** deals `{boss_dmg}` damage to **{target_player.display_name}'s {target_card['name']}**!")

        # End player's turn
        self.player_turns[player.id] = False

        await self.process_turn(interaction)

    async def process_turn(self, interaction):
        """Process turn logic and check for win/lose conditions"""
        self.turn += 1

        # Check if boss is defeated
        if self.boss_hp <= 0:
            await self.end_raid(True)
            return

        # Check if all players are defeated
        all_alive = False
        for team_data in self.player_teams_battle:
            for card in team_data['cards']:
                if card['hp'] > 0:
                    all_alive = True
                    break
            if all_alive:
                break

        if not all_alive or self.turn >= self.max_turns:
            await self.end_raid(False)
            return

        # Reset turns for next round
        if all(not acted for acted in self.player_turns.values()):
            for player_id in self.player_turns:
                self.player_turns[player_id] = True

        await self.update_raid_display(interaction)

    async def update_raid_display(self, interaction):
        """Update the raid display"""
        self.update_view_buttons()

        embed = discord.Embed(
            title=f"🐉 Boss Raid: {self.boss['name']}",
            description=f"Turn `{self.turn}`/`{self.max_turns}`",
            color=0xDC143C
        )

        # Boss HP
        boss_hp_percent = (self.boss_hp / self.boss_max_hp) * 100
        embed.add_field(
            name=f"🐉 {self.boss['name']} HP",
            value=f"`{self.boss_hp}`/`{self.boss_max_hp}` ({boss_hp_percent:.1f}%)",
            inline=False
        )

        # Show all players' teams
        for team_data in self.player_teams_battle:
            player = team_data['player']
            cards = team_data['cards']

            team_status = []
            for card in cards:
                hp_percent = (card['hp'] / card['max_hp']) * 100
                status = "💀" if card['hp'] <= 0 else "✅"
                turn_status = "🔄" if self.player_turns.get(
                    player.id, False) else "⏸️"
                team_status.append(
                    f"{status}{turn_status} **{card['name']}**: `{card['hp']}`/`{card['max_hp']}` ({hp_percent:.1f}%)")

            embed.add_field(
                name=f"🃏 {player.display_name}'s Team",
                value="\n".join(team_status),
                inline=False
            )

        # Current turn indicator
        current_player = None
        for player, _ in self.all_players:
            if self.player_turns.get(player.id, False):
                current_player = player
                break

        if current_player:
            embed.add_field(
                name="🎯 Current Turn",
                value=f"**{current_player.display_name}** - Choose your action!",
                inline=False
            )

        # Battle log (last 5 entries)
        if self.log:
            recent_log = self.log[-5:]
            embed.add_field(
                name="📜 Battle Log",
                value="\n".join(recent_log),
                inline=False
            )

        embed.set_footer(text="⚔️ Attack | 🛡️ Defend | 💚 Heal | ⏭️ End Turn")

        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_button_click(self, interaction: discord.Interaction):
        """Handle button clicks"""
        if not self.raid_active:
            await interaction.response.send_message("The raid has ended!", ephemeral=True)
            return

        # Find current player
        current_player = None
        for player, _ in self.all_players:
            if self.player_turns.get(player.id, False):
                current_player = player
                break

        if not current_player or interaction.user.id != current_player.id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        custom_id = interaction.data['custom_id']

        if custom_id.startswith('card_'):
            # Card attack
            parts = custom_id.split('_')
            player_id = int(parts[1])
            card_name = '_'.join(parts[2:])  # Handle card names with spaces

            await self.handle_card_attack(interaction, current_player, card_name)

        elif custom_id == 'defend':
            # Defend action
            self.log.append(
                f"🛡️ **{current_player.display_name}**'s team takes a defensive stance!")

            # Boss attacks with reduced damage
            if self.boss_hp > 0:
                all_alive_cards = []
                for team_data in self.player_teams_battle:
                    for card in team_data['cards']:
                        if card['hp'] > 0:
                            all_alive_cards.append((team_data['player'], card))

                if all_alive_cards:
                    target_player, target_card = random.choice(all_alive_cards)
                    boss_dmg = int(self.boss['atk'] *
                                   (0.5 + random.random() * 0.2))
                    target_card['hp'] = max(0, target_card['hp'] - boss_dmg)
                    self.log.append(
                        f"🛡️ **{self.boss['name']}** deals `{boss_dmg}` reduced damage to **{target_player.display_name}'s {target_card['name']}**!")

            self.player_turns[current_player.id] = False
            await self.process_turn(interaction)

        elif custom_id == 'heal':
            # Heal action
            alive_cards = self.get_alive_cards(current_player.id)
            if not alive_cards:
                await interaction.response.send_message("No alive cards to heal!", ephemeral=True)
                return

            target_card = random.choice(alive_cards)
            heal_amount = int(target_card['max_hp'] * 0.3)
            target_card['hp'] = min(
                target_card['max_hp'], target_card['hp'] + heal_amount)
            self.log.append(
                f"💚 **{current_player.display_name}'s {target_card['name']}** heals for `{heal_amount}` HP!")

            # Boss still attacks
            if self.boss_hp > 0:
                all_alive_cards = []
                for team_data in self.player_teams_battle:
                    for card in team_data['cards']:
                        if card['hp'] > 0:
                            all_alive_cards.append((team_data['player'], card))

                if all_alive_cards:
                    target_player, target_card = random.choice(all_alive_cards)
                    boss_dmg = int(self.boss['atk'] *
                                   (0.9 + random.random() * 0.3))
                    target_card['hp'] = max(0, target_card['hp'] - boss_dmg)
                    self.log.append(
                        f"💀 **{self.boss['name']}** deals `{boss_dmg}` damage to **{target_player.display_name}'s {target_card['name']}**!")

            self.player_turns[current_player.id] = False
            await self.process_turn(interaction)

        elif custom_id == 'end_turn':
            # End turn without action
            self.log.append(
                f"⏭️ **{current_player.display_name}** ends their turn!")
            self.player_turns[current_player.id] = False
            await self.process_turn(interaction)

    async def end_raid(self, victory):
        """End the boss raid"""
        self.raid_active = False

        users = load(USERS_FILE)

        if victory:
            # Victory rewards for all players
            embed = discord.Embed(
                title="🎉 Boss Raid Victory!",
                description=f"You defeated **{self.boss['name']}**!",
                color=0x2ECC71
            )

            for player, original_cards in self.all_players:
                user = self.ensure_user(users, str(player.id))

                # Random reward
                rewards = random.choice([
                    ("aura", random.randint(100, 500)),
                    ("tickets", random.randint(1, 3)),
                    ("chest", "common")
                ])

                if rewards[0] == "aura":
                    user.setdefault('aura_balance', 0)
                    user['aura_balance'] += rewards[1]
                elif rewards[0] == "tickets":
                    user.setdefault('tickets', {})
                    user['tickets'].setdefault('raid', 0)
                    user['tickets']['raid'] += rewards[1]
                else:
                    user.setdefault('chests', {})
                    user['chests'].setdefault('common', 0)
                    user['chests']['common'] += 1

                # Grant EXP rewards for surviving cards
                team_data = next(
                    (td for td in self.player_teams_battle if td['player'].id == player.id), None)
                if team_data:
                    winner_cards = [c["name"]
                                    for c in team_data['cards'] if c['hp'] > 0]
                    if winner_cards:
                        battle_rewards = self._grant_battle_rewards(
                            player.id, 0, winner_cards, [])
                        if battle_rewards['card_levelups']:
                            embed.add_field(name=f"⭐ {player.display_name}'s Level Ups!", value=", ".join(
                                battle_rewards['card_levelups']), inline=False)
        else:
            embed = discord.Embed(
                title="💀 Boss Raid Defeated",
                description=f"Your team was defeated by **{self.boss['name']}**...",
                color=0xE74C3C
            )

        save(USERS_FILE, users)

        # Disable all buttons
        for child in self.children:
            child.disabled = True

        await self.ctx.message.edit(embed=embed, view=self)


def setup(bot):
    bot.add_cog(Combat(bot))
