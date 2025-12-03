import discord
import time
import random
from discord.ext import commands
from discord.ui import View, Button
from utils.database import load, save
from utils.game_math import compute_stats
import config

CREWS_FILE = "data/crews.json"
USERS_FILE = "data/users.json"
GANGS_FILE = "data/gangs.json"
WHITETIGER_FILE = "data/whitetiger.json"


class CaptureBattleView(View):
    """Interactive battle UI for territory capture with clean vertical layout"""

    def __init__(self, ctx, my_team, en_team, defender_name, ensure_user_func, on_end_callback):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.my_team = my_team
        self.en_team = en_team
        self.defender_name = defender_name
        self.ensure_user = ensure_user_func
        self.on_end = on_end_callback
        self.turn = 0
        self.max_turns = 15
        self.my_team_battle = [{"name": c["name"], "atk": c["atk"],
                                "hp": c["hp"], "max_hp": c["max_hp"]} for c in my_team]
        self.en_team_battle = [{"name": c["name"], "atk": c["atk"],
                                "hp": c["hp"], "max_hp": c["max_hp"]} for c in en_team]
        self.log = []
        self.battle_active = True
        self.msg = None

        for i in range(min(len(my_team), 4)):
            self.add_item(CaptureAttackButton(i + 1, my_team[i]['name'], i))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            try:
                await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return False
        if not self.battle_active:
            try:
                await interaction.response.send_message("❌ Battle has ended!", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return False
        return True

    async def process_attack(self, interaction, card_index):
        if card_index < 0 or card_index >= len(self.my_team_battle):
            await interaction.response.send_message("❌ Invalid card selection!", ephemeral=True)
            return

        attacker = self.my_team_battle[card_index]
        if attacker['hp'] <= 0:
            await interaction.response.send_message("❌ This card is already defeated!", ephemeral=True)
            return

        p2_alive = [c for c in self.en_team_battle if c['hp'] > 0]
        if not p2_alive:
            await interaction.response.defer()
            await self.end_battle(True)
            return

        d = random.choice(p2_alive)
        dmg = int(attacker['atk'] * (0.8 + random.random() * 0.4))
        d['hp'] = max(0, d['hp'] - dmg)
        hp_percent = int((d['hp'] / d['max_hp']) *
                         100) if d['max_hp'] > 0 else 0
        self.log.append(
            f"🔵 **{attacker['name']}** → **{d['name']}** `{dmg}` dmg ({hp_percent}% HP)")

        p1_alive = [c for c in self.my_team_battle if c['hp'] > 0]
        if p1_alive and any(c['hp'] > 0 for c in self.en_team_battle):
            e = random.choice([c for c in self.en_team_battle if c['hp'] > 0])
            t = random.choice(p1_alive)
            edmg = int(e['atk'] * (0.8 + random.random() * 0.4))
            t['hp'] = max(0, t['hp'] - edmg)
            thp_percent = int((t['hp'] / t['max_hp']) *
                              100) if t['max_hp'] > 0 else 0
            self.log.append(
                f"🔴 **{e['name']}** → **{t['name']}** `{edmg}` dmg ({thp_percent}% HP)")

        self.turn += 1

        p1_alive = [c for c in self.my_team_battle if c['hp'] > 0]
        p2_alive = [c for c in self.en_team_battle if c['hp'] > 0]

        if not p1_alive or not p2_alive or self.turn >= self.max_turns:
            await interaction.response.defer()
            await self.end_battle(any(c['hp'] > 0 for c in self.my_team_battle))
        else:
            await self.update_battle_embed(interaction)

    async def update_battle_embed(self, interaction):
        p1_alive = [c for c in self.my_team_battle if c['hp'] > 0]
        p2_alive = [c for c in self.en_team_battle if c['hp'] > 0]

        embed = discord.Embed(
            title="⚔️ Territory Battle",
            description=f"**Turn {self.turn}**\n\n🔵 **{self.ctx.author.display_name}** vs 🔴 **{self.defender_name}**",
            color=0xF1C40F
        )
        embed.set_author(name="Territory Capture",
                         icon_url=self.ctx.author.display_avatar.url)

        my_team_text = "\n".join([
            f"• **{c['name']}** (Str: {c['atk']} | HP: {c['hp']}/{c['max_hp']})"
            for c in self.my_team_battle
        ])
        en_team_text = "\n".join([
            f"• **{c['name']}** (Str: {c['atk']} | HP: {c['hp']}/{c['max_hp']})"
            for c in self.en_team_battle
        ])

        embed.add_field(name="🔵 Your Team", value=my_team_text, inline=False)
        embed.add_field(name="🔴 Defenders", value=en_team_text, inline=False)

        if self.log:
            recent_log = "\n".join(self.log[-5:])
            embed.add_field(name="📋 Recent Actions",
                            value=recent_log, inline=False)

        embed.set_footer(text="Choose a card button below to attack!")
        await interaction.response.edit_message(embed=embed, view=self)

    async def end_battle(self, p1_win):
        self.battle_active = False
        await self.on_end(p1_win, self.log[:])
        result_embed = discord.Embed(
            title="🏴 Territory Battle Result",
            description=f"{'You won!' if p1_win else 'You were defeated.'}\n\n**Highlights:**\n" +
            "\n".join(self.log[:10]),
            color=0x2ECC71 if p1_win else 0xE74C3C
        )
        result_embed.set_author(name="Territory Capture",
                                icon_url=self.ctx.author.display_avatar.url)
        await self.msg.edit(embed=result_embed, view=None)


class CaptureAttackButton(Button):
    def __init__(self, card_num, card_name, card_index):
        super().__init__(
            label=f"Card {card_num}: {card_name[:15]}", style=discord.ButtonStyle.primary, row=(card_num - 1) // 2
        )
        self.card_index = card_index
        self.card_name = card_name

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, CaptureBattleView):
            await view.process_attack(interaction, self.card_index)


class Crew(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
                "crew_name": None
            }
        return users[uid]

    def get_gang_for_user(self, uid):
        """Find gang (if any) for a user by scanning gangs.json."""
        try:
            gangs = load(GANGS_FILE)
        except Exception:
            return None, None
        uid_str = str(uid)
        for gid, g in gangs.items():
            if uid_str in g.get("members", []):
                return gid, g
        return None, None

    def get_crew(self, uid):
        """Get crew that user belongs to (existing helper, kept)."""
        crews = load(CREWS_FILE)
        for cid, crew in crews.items():
            if str(uid) in crew.get('members', []):
                return cid, crew
        return None, None

    def _get_player_faction(self, uid):
        """Return ('gang' or 'crew', id, data) for the player's faction, preferring gang if in both."""
        gid, gang = self.get_gang_for_user(uid)
        if gang:
            return "gang", gid, gang
        cid, crew = self.get_crew(uid)
        if crew:
            return "crew", cid, crew
        return None, None, None

    def _build_player_team(self, uid):
        """Build a simple battle team (up to 4 cards) for a player using compute_stats.

        This mirrors the logic from the Combat cog: prefer user['team'] names, fall back to first 4 cards.
        Returns a list of dicts: {name, atk, hp, max_hp}.
        """
        users = load(USERS_FILE)
        cards_db = load(config.CARDS_FILE) if hasattr(
            config, "CARDS_FILE") else load("data/cards.json")
        uid_str = str(uid)
        user = users.get(uid_str)
        if not user:
            return []

        user.setdefault("cards", [])
        user.setdefault("team", [])

        owned_cards = user.get("cards", [])
        if not owned_cards:
            return []

        def find_owned_card_by_name(name: str):
            for c in owned_cards:
                if c.get("name") == name:
                    return c
            return None

        team_data = []
        team_names = user.get("team", [])

        if team_names:
            for name in team_names[:4]:
                owned = find_owned_card_by_name(name)
                if not owned:
                    continue
                base = next((v for v in cards_db.values() if v.get(
                    "name") == owned.get("name")), None)
                if not base:
                    continue
                stats = compute_stats(base, owned.get("level", 1), owned.get(
                    "aura", 0), owned.get("equipped_item_id"))
                atk = int(stats["attack"])
                hp = int(stats["health"])
                team_data.append(
                    {"name": owned["name"], "atk": atk, "hp": hp, "max_hp": hp})

        if not team_data:
            for c in owned_cards[:4]:
                base = next((v for v in cards_db.values()
                            if v.get("name") == c.get("name")), None)
                if not base:
                    continue
                stats = compute_stats(base, c.get("level", 1), c.get(
                    "aura", 0), c.get("equipped_item_id"))
                atk = int(stats["attack"])
                hp = int(stats["health"])
                team_data.append(
                    {"name": c["name"], "atk": atk, "hp": hp, "max_hp": hp})

        return team_data

    def get_crew(self, uid):
        """Get crew that user belongs to"""
        crews = load(CREWS_FILE)
        for cid, crew in crews.items():
            if str(uid) in crew.get('members', []):
                return cid, crew
        return None, None

    def _simulate_simple_battle(self, atk_team, def_team):
        """Run a simple turn-based battle between two teams.

        Returns (attacker_won: bool, log_lines: list[str]).
        """
        atk = [{"name": c["name"], "atk": c["atk"], "hp": c["hp"],
                "max_hp": c.get("max_hp", c["hp"])} for c in atk_team]
        deff = [{"name": c["name"], "atk": c["atk"], "hp": c["hp"],
                 "max_hp": c.get("max_hp", c["hp"])} for c in def_team]
        log = []
        turn = 0
        max_turns = 20

        while turn < max_turns and any(c["hp"] > 0 for c in atk) and any(c["hp"] > 0 for c in deff):
            turn += 1
            atk_alive = [c for c in atk if c["hp"] > 0]
            def_alive = [c for c in deff if c["hp"] > 0]
            if not atk_alive or not def_alive:
                break

            a = random.choice(atk_alive)
            d = random.choice(def_alive)
            dmg = int(a["atk"] * (0.8 + random.random() * 0.4))
            d["hp"] = max(0, d["hp"] - dmg)
            hp_percent = int((d["hp"] / d["max_hp"]) *
                             100) if d["max_hp"] > 0 else 0
            log.append(
                f"🔵 {a['name']} → {d['name']} `{dmg}` dmg ({hp_percent}% HP)")

            def_alive = [c for c in deff if c["hp"] > 0]
            atk_alive = [c for c in atk if c["hp"] > 0]
            if not def_alive or not atk_alive:
                break

            e = random.choice(def_alive)
            t = random.choice(atk_alive)
            edmg = int(e["atk"] * (0.8 + random.random() * 0.4))
            t["hp"] = max(0, t["hp"] - edmg)
            thp_percent = int((t["hp"] / t["max_hp"]) *
                              100) if t["max_hp"] > 0 else 0
            log.append(
                f"🔴 {e['name']} → {t['name']} `{edmg}` dmg ({thp_percent}% HP)")

        atk_alive = any(c["hp"] > 0 for c in atk)
        def_alive = any(c["hp"] > 0 for c in deff)

        if atk_alive and not def_alive:
            return True, log
        if def_alive and not atk_alive:
            return False, log
        return atk_alive, log

    @commands.command(name="crew")
    async def crew(self, ctx, action: str = None, *, arg: str = ""):
        """Crew commands. Only 4 crews can exist in the entire bot."""
        if action == "create":
            if not arg:
                embed = discord.Embed(
                    title="❌ No Name Provided",
                    description="Usage: `ls crew create <name>`\n\nExample: `ls crew create Workers`",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            crews = load(CREWS_FILE)

            # Check if 4 crews already exist
            if len(crews) >= 4:
                embed = discord.Embed(
                    title="❌ Crew Limit Reached",
                    description="Maximum 4 crews can exist in the entire bot!\n\nAll crew slots are currently taken.",
                    color=0xE74C3C
                )
                crew_list = "\n".join(
                    [f"• **{c['name']}**" for c in crews.values()])
                embed.add_field(name="Existing Crews",
                                value=crew_list, inline=False)
                return await ctx.send(embed=embed)

            # Check if user is already in a crew
            cid, existing_crew = self.get_crew(ctx.author.id)
            if existing_crew:
                embed = discord.Embed(
                    title="❌ Already in a Crew",
                    description=f"You're already in **{existing_crew['name']}**!",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            # Check if crew name already exists
            if any(c['name'].lower() == arg.lower() for c in crews.values()):
                embed = discord.Embed(
                    title="❌ Crew Name Taken",
                    description=f"A crew named **{arg}** already exists!",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            cid = str(int(time.time()))
            new_crew = {
                "id": cid,
                "name": arg,
                "leader": str(ctx.author.id),
                "members": [str(ctx.author.id)],
                "territories": [],
                "created_at": int(time.time())
            }

            crews[cid] = new_crew
            save(CREWS_FILE, crews)

            users = load(USERS_FILE)
            user = self.ensure_user(users, str(ctx.author.id))
            user["crew_name"] = arg
            save(USERS_FILE, users)

            embed = discord.Embed(
                title="✅ Crew Created!",
                description=f"**{arg}** has been created!",
                color=0x2ECC71
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            embed.add_field(name="👑 Leader",
                            value=f"<@{ctx.author.id}>", inline=True)
            embed.add_field(name="👥 Members", value="`1`", inline=True)
            embed.add_field(name="🗺️ Territories", value="`0`", inline=True)
            embed.add_field(name="📊 Crew Count",
                            value=f"`{len(crews)}/4`", inline=True)
            embed.set_footer(text="Use `ls crew add @user` to add members!")
            await ctx.send(embed=embed)

        elif action == "info":
            cid, crew = self.get_crew(ctx.author.id)
            if not crew:
                embed = discord.Embed(
                    title="❌ Not in a Crew",
                    description="You're not in a crew! Create one with `ls crew create <name>`",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            members_list = "\n".join(
                [f"• <@{uid}>" + (" 👑" if uid == crew['leader'] else "") for uid in crew.get('members', [])])
            territories_list = "\n".join(
                [f"• {t}" for t in crew.get('territories', [])]) or "None"

            embed = discord.Embed(
                title=f"🏛️ {crew['name']}",
                color=0x9B59B6
            )
            embed.set_author(name="Crew Information",
                             icon_url=ctx.author.display_avatar.url)
            embed.add_field(name="👑 Leader",
                            value=f"<@{crew['leader']}>", inline=True)
            embed.add_field(
                name="👥 Members", value=f"`{len(crew.get('members', []))}`", inline=True)
            embed.add_field(
                name="🗺️ Territories", value=f"`{len(crew.get('territories', []))}`", inline=True)
            embed.add_field(name="📋 Members List",
                            value=members_list[:1024] or "None", inline=False)
            embed.add_field(name="🗺️ Territories",
                            value=territories_list[:1024] or "None", inline=False)
            await ctx.send(embed=embed)

        elif action == "list":
            crews = load(CREWS_FILE)
            if not crews:
                embed = discord.Embed(
                    title="🏛️ Crews",
                    description="No crews exist yet!",
                    color=0x95A5A6
                )
                return await ctx.send(embed=embed)

            crew_list = []
            for crew in crews.values():
                crew_list.append(
                    f"**{crew['name']}** - {len(crew.get('members', []))} members - {len(crew.get('territories', []))} territories")

            embed = discord.Embed(
                title="🏛️ All Crews",
                description="\n".join(crew_list) or "No crews",
                color=0x9B59B6
            )
            embed.set_footer(text=f"Total: {len(crews)}/4 crews")
            await ctx.send(embed=embed)

        elif action == "leave":
            cid, crew = self.get_crew(ctx.author.id)
            if not crew:
                embed = discord.Embed(
                    title="❌ Not in a Crew",
                    description="You're not in a crew!",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            if crew['leader'] == str(ctx.author.id):
                embed = discord.Embed(
                    title="❌ Leader Cannot Leave",
                    description="The leader cannot leave! Transfer leadership first.",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            crew['members'].remove(str(ctx.author.id))
            crews = load(CREWS_FILE)
            crews[cid] = crew
            save(CREWS_FILE, crews)

            users = load(USERS_FILE)
            if str(ctx.author.id) in users:
                users[str(ctx.author.id)]["crew_name"] = None
            save(USERS_FILE, users)

            embed = discord.Embed(
                title="✅ Left Crew",
                description=f"You left **{crew['name']}**",
                color=0x2ECC71
            )
            await ctx.send(embed=embed)

    @commands.command(name="capture")
    async def capture(self, ctx, *, territory_name: str = None):
        """Fight to capture a territory for your gang or crew. Usage: ls capture <territory_name>"""
        if not territory_name:
            return await ctx.send("❌ Usage: `ls capture <territory_name>`")

        f_type, f_id, faction = self._get_player_faction(ctx.author.id)
        if not faction:
            embed = discord.Embed(
                title="❌ No Faction",
                description="You are not in any gang or crew. Join or create one to capture territories.",
                color=0xE74C3C,
            )
            return await ctx.send(embed=embed)

        gangs = load(GANGS_FILE)
        crews = load(CREWS_FILE)
        territory_name_clean = territory_name.strip()
        owner_type = None
        owner_id = None
        owner = None

        for gid, g in gangs.items():
            terrs = g.get("territories", [])
            for t in terrs:
                if str(t).lower() == territory_name_clean.lower():
                    owner_type = "gang"
                    owner_id = gid
                    owner = g
                    break
            if owner:
                break

        if not owner:
            for cid, c in crews.items():
                terrs = c.get("territories", [])
                for t in terrs:
                    if str(t).lower() == territory_name_clean.lower():
                        owner_type = "crew"
                        owner_id = cid
                        owner = c
                        break
                if owner:
                    break

        attacker_team = self._build_player_team(ctx.author.id)
        if not attacker_team:
            embed = discord.Embed(
                title="❌ No Team",
                description="You have no battle team. Use `ls teamadd` to set up your cards first.",
                color=0xE74C3C,
            )
            return await ctx.send(embed=embed)

        white_agents = load(WHITETIGER_FILE)

        if not owner:
            base_npcs = [
                {"name": "Daniel Park", "atk": 320, "hp": 3800},
                {"name": "Vasco", "atk": 310, "hp": 3900},
                {"name": "Zack Lee", "atk": 330, "hp": 3700},
                {"name": "Gun Park", "atk": 380, "hp": 4200},
                {"name": "Jake Kim", "atk": 340, "hp": 4000},
                {"name": "Eugene", "atk": 300, "hp": 3600},
            ]
            random.shuffle(base_npcs)
            chosen = base_npcs[:4]
            npc_team = []
            for c in chosen:
                hp = int(c.get("hp", 1))
                npc_team.append({"name": c.get("name", "NPC"), "atk": int(
                    c.get("atk", 1)), "hp": hp, "max_hp": hp})

            defender_name = "Territory Enforcers"
            # Start interactive battle
            embed = discord.Embed(
                title="⚔️ Territory Battle Starting",
                description=f"You're challenging **{defender_name}** for **{territory_name_clean}**!",
                color=0xF1C40F
            )
            embed.set_author(name="Territory Capture",
                             icon_url=ctx.author.display_avatar.url)
            embed.set_footer(text="Prepare for battle!")
            msg = await ctx.send(embed=embed)
            view = CaptureBattleView(ctx, attacker_team, npc_team, defender_name, self.ensure_user, lambda won, log: self._handle_capture_end(
                ctx, won, log, territory_name_clean, f_type, f_id, faction, None, None))
            view.msg = msg
            await msg.edit(view=view)
            return

        if owner_type == f_type and owner_id == f_id:
            embed = discord.Embed(
                title="ℹ️ Already Owned",
                description=f"Your {f_type} already controls **{territory_name_clean}**.",
                color=0x95A5A6,
            )
            return await ctx.send(embed=embed)

        if owner_type == "gang":
            defense_id = owner.get("defense_agent")
            def_team = []
            if defense_id and defense_id in white_agents:
                agent = white_agents[defense_id]
                for c in agent.get("team", []):
                    hp = int(c.get("hp", 1))
                    def_team.append({"name": c.get("name", "Agent"), "atk": int(
                        c.get("atk", 1)), "hp": hp, "max_hp": hp})
                defender_name = agent.get("name", "White Tiger Agent")
            else:
                try:
                    leader_id = int(owner.get("leader"))
                except Exception:
                    leader_id = None
                if leader_id is None:
                    embed = discord.Embed(
                        title="❌ No Defense Team",
                        description="Defending gang has no valid defense setup.",
                        color=0xE74C3C,
                    )
                    return await ctx.send(embed=embed)
                def_team = self._build_player_team(leader_id)
                defender_name = f"Leader of {owner.get('name', 'Unknown')}"
        else:
            try:
                leader_id = int(owner.get("leader"))
            except Exception:
                leader_id = None
            if leader_id is None:
                embed = discord.Embed(
                    title="❌ No Defense Team",
                    description="Defending crew has no valid defense setup.",
                    color=0xE74C3C,
                )
                return await ctx.send(embed=embed)
            def_team = self._build_player_team(leader_id)
            defender_name = f"Leader of {owner.get('name', 'Unknown')}"

        if not def_team:
            embed = discord.Embed(
                title="❌ No Defense Team",
                description="Defending side has no battle team configured.",
                color=0xE74C3C,
            )
            return await ctx.send(embed=embed)

        # Start interactive battle for claimed territory
        embed = discord.Embed(
            title="⚔️ Territory Battle Starting",
            description=f"You're challenging **{defender_name}** for **{territory_name_clean}**!",
            color=0xF1C40F
        )
        embed.set_author(name="Territory Capture",
                         icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Prepare for battle!")
        msg = await ctx.send(embed=embed)
        view = CaptureBattleView(ctx, attacker_team, def_team, defender_name, self.ensure_user, lambda won, log: self._handle_capture_end(
            ctx, won, log, territory_name_clean, f_type, f_id, faction, owner_type, owner_id))
        view.msg = msg
        await msg.edit(view=view)

    def _handle_capture_end(self, ctx, attacker_won, log_lines, territory_name_clean, f_type, f_id, faction, owner_type, owner_id):
        """Callback after interactive capture battle concludes to transfer territory if won"""
        if not attacker_won:
            # Battle lost; nothing to transfer
            return

        gangs = load(GANGS_FILE)
        crews = load(CREWS_FILE)

        # Remove territory from previous owner (if any)
        if owner_type and owner_id:
            if owner_type == "gang":
                owner = gangs.get(owner_id)
                if owner:
                    owner.setdefault("territories", [])
                    owner["territories"] = [t for t in owner["territories"]
                                            if str(t).lower() != territory_name_clean.lower()]
                    gangs[owner_id] = owner
                    save(GANGS_FILE, gangs)
            else:
                owner = crews.get(owner_id)
                if owner:
                    owner.setdefault("territories", [])
                    owner["territories"] = [t for t in owner["territories"]
                                            if str(t).lower() != territory_name_clean.lower()]
                    crews[owner_id] = owner
                    save(CREWS_FILE, crews)

        # Add territory to attacker's faction
        if f_type == "gang":
            faction.setdefault("territories", [])
            if territory_name_clean not in faction["territories"]:
                faction["territories"].append(territory_name_clean)
            gangs[f_id] = faction
            save(GANGS_FILE, gangs)
        else:
            faction.setdefault("territories", [])
            if territory_name_clean not in faction["territories"]:
                faction["territories"].append(territory_name_clean)
            crews[f_id] = faction
            save(CREWS_FILE, crews)

    @commands.command(name="crew_add", aliases=["crewadd"])
    async def crew_add(self, ctx, member: discord.Member = None):
        """Add a member to your crew. Usage: ls crew_add @user"""
        if not member:
            embed = discord.Embed(
                title="❌ No Member Specified",
                description="Usage: `ls crew_add @user`",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if member.bot:
            embed = discord.Embed(
                title="❌ Cannot Add Bots",
                description="Bots cannot join crews!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        cid, crew = self.get_crew(ctx.author.id)
        if not crew or crew['leader'] != str(ctx.author.id):
            embed = discord.Embed(
                title="❌ Leader Only",
                description="Only the crew leader can add members!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Check if target is already in a crew
        target_cid, target_crew = self.get_crew(member.id)
        if target_crew:
            embed = discord.Embed(
                title="❌ Already in a Crew",
                description=f"{member.display_name} is already in **{target_crew['name']}**!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if str(member.id) in crew.get('members', []):
            embed = discord.Embed(
                title="❌ Already a Member",
                description=f"{member.display_name} is already in your crew!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        crew.setdefault('members', []).append(str(member.id))
        crews = load(CREWS_FILE)
        crews[cid] = crew
        save(CREWS_FILE, crews)

        users = load(USERS_FILE)
        user = self.ensure_user(users, str(member.id))
        user["crew_name"] = crew['name']
        save(USERS_FILE, users)

        embed = discord.Embed(
            title="✅ Member Added",
            description=f"{member.mention} has been added to **{crew['name']}**!",
            color=0x2ECC71
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="👥 Total Members",
                        value=f"`{len(crew.get('members', []))}`", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="crew_remove", aliases=["crewremove", "crewkick"])
    async def crew_remove(self, ctx, member: discord.Member = None):
        """Remove a member from your crew. Usage: ls crew_remove @user"""
        if not member:
            embed = discord.Embed(
                title="❌ No Member Specified",
                description="Usage: `ls crew_remove @user`",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        cid, crew = self.get_crew(ctx.author.id)
        if not crew or crew['leader'] != str(ctx.author.id):
            embed = discord.Embed(
                title="❌ Leader Only",
                description="Only the crew leader can remove members!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if str(member.id) not in crew.get('members', []):
            embed = discord.Embed(
                title="❌ Not a Member",
                description=f"{member.display_name} is not in your crew!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if crew['leader'] == str(member.id):
            embed = discord.Embed(
                title="❌ Cannot Remove Leader",
                description="You cannot remove yourself as leader!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        crew['members'].remove(str(member.id))
        crews = load(CREWS_FILE)
        crews[cid] = crew
        save(CREWS_FILE, crews)

        users = load(USERS_FILE)
        if str(member.id) in users:
            users[str(member.id)]["crew_name"] = None
        save(USERS_FILE, users)

        embed = discord.Embed(
            title="✅ Member Removed",
            description=f"{member.mention} has been removed from **{crew['name']}**",
            color=0xE74C3C
        )
        await ctx.send(embed=embed)

    @commands.command(name="map", aliases=["territory", "territories"])
    async def map(self, ctx):
        """View the territory map showing both gang and crew control"""
        from utils.database import load as _load  # local alias to avoid confusion

        crews = _load(CREWS_FILE)
        gangs = _load("data/gangs.json")

        embed = discord.Embed(
            title="🗺️ Territory Map",
            description="Current territory control across gangs and crews",
            color=0x3498DB,
        )

        # Always use the provided static image
        embed.set_image(url="https://cdn.discordapp.com/attachments/1439586635900518472/1444523404194611280/955bc55c-7e2c-4671-b799-80d607ff3187-md.jpg?ex=692d04c1&is=692bb341&hm=a0bb5c7781f58eb559f5bb90c8cafde8fc6e95b0df1436c9924a11b3bc9d14bf&")

        # Gang territories
        gang_lines = []
        for g in gangs.values():
            name = g.get("name", "Unknown")
            terrs = g.get("territories", [])
            if terrs:
                gang_lines.append(
                    f"**{name}**: {', '.join(str(t) for t in terrs)}")
        if gang_lines:
            embed.add_field(
                name="👥 Gang Territories",
                value="\n".join(gang_lines)[:1024],
                inline=False,
            )
        else:
            embed.add_field(
                name="👥 Gang Territories",
                value="No gangs have claimed territories yet.",
                inline=False,
            )

        # Crew territories
        crew_lines = []
        for crew in crews.values():
            name = crew.get("name", "Unknown")
            terrs = crew.get("territories", [])
            if terrs:
                crew_lines.append(
                    f"**{name}**: {', '.join(str(t) for t in terrs)}")
        if crew_lines:
            embed.add_field(
                name="🏛️ Crew Territories",
                value="\n".join(crew_lines)[:1024],
                inline=False,
            )
        else:
            embed.add_field(
                name="🏛️ Crew Territories",
                value="No crews have claimed territories yet.",
                inline=False,
            )

        embed.set_footer(
            text="Territories are controlled by gangs and crews. Win battles and events to claim more!")
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Crew(bot))
