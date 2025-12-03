import discord
import random
import asyncio
from discord.ext import commands
from discord.ui import View, Button
from utils.database import load, save
from utils.battle_engine import BattleEngine
from utils.game_math import compute_stats

BOSSES_FILE = "data/bosses.json"
USERS_FILE = "data/users.json"
CARDS_FILE = "data/cards.json"

# Memory Lobby: { "CODE": { "host": int, "boss": str, "members": [int] } }
active_lobbies = {}


class LobbyView(View):
    def __init__(self, code, boss_data, max_players):
        super().__init__(timeout=600)
        self.code = code
        self.boss = boss_data
        self.max = max_players

    @discord.ui.button(label="Join Raid", style=discord.ButtonStyle.green, emoji="⚔️")
    async def join(self, button, interaction):
        lobby = active_lobbies.get(self.code)
        if not lobby:
            return await interaction.response.send_message("❌ Lobby has expired or been closed.", ephemeral=True)

        if len(lobby['members']) >= self.max:
            return await interaction.response.send_message("❌ Lobby is full!", ephemeral=True)

        if interaction.user.id in lobby['members']:
            return await interaction.response.send_message("✅ You're already in this raid!", ephemeral=True)

        lobby['members'].append(interaction.user.id)

        # Update embed
        embed = interaction.message.embeds[0]
        members_list = "\n".join([f"• <@{uid}>" for uid in lobby['members']])
        embed.set_field_at(
            1, name=f"👥 Members ({len(lobby['members'])}/{self.max})", value=members_list or "None", inline=False)

        await interaction.response.edit_message(embed=embed)
        await interaction.followup.send(f"✅ Joined raid! ({len(lobby['members'])}/{self.max})", ephemeral=True)

    @discord.ui.button(label="Start Raid", style=discord.ButtonStyle.danger, emoji="🚀")
    async def start(self, button, interaction):
        lobby = active_lobbies.get(self.code)
        if not lobby:
            return await interaction.response.send_message("❌ Lobby not found.", ephemeral=True)

        if interaction.user.id != lobby['host']:
            return await interaction.response.send_message("❌ Only the host can start the raid!", ephemeral=True)

        if len(lobby['members']) < 1:
            return await interaction.response.send_message("❌ Need at least 1 member to start!", ephemeral=True)

        # Cleanup
        del active_lobbies[self.code]
        await interaction.response.edit_message(
            content="⚔️ **Raid Starting...**",
            view=None,
            embed=None
        )

        # --- BATTLE LOGIC ---
        users = load(USERS_FILE)
        cards_db = load(CARDS_FILE)

        team_cards = []

        # Get cards from all players
        for uid in lobby['members']:
            user_cards = users.get(str(uid), {}).get("cards", [])
            # Take top 2 cards per player
            for c in user_cards[:2]:
                base = next((v for v in cards_db.values()
                            if v['name'] == c['name']), None)
                if base:
                    stats = compute_stats(base, c['level'], c.get(
                        'aura', 0), c.get('equipped_item_id'))
                    team_cards.append(
                        {"name": c['name'], "atk": stats['attack'], "hp": stats['health']})

        if not team_cards:
            embed = discord.Embed(
                title="❌ Raid Failed",
                description="No cards found in party. Make sure all members have cards!",
                color=0xE74C3C
            )
            return await interaction.channel.send(embed=embed)

        # Simulate
        result = BattleEngine.simulate_raid(team_cards, self.boss['stats'])

        # Battle result embed
        result_embed = discord.Embed(
            title=f"⚔️ Raid: {self.boss['name']}",
            description=result['log'][:2000],
            color=0x2ECC71 if result['win'] else 0xE74C3C
        )
        result_embed.set_author(
            name="Raid Battle Results", icon_url=interaction.user.display_avatar.url)

        if self.boss.get('image'):
            result_embed.set_thumbnail(url=self.boss['image'])

        result_embed.add_field(
            name="🎯 Result",
            value="✅ **VICTORY!**" if result['win'] else "❌ **DEFEAT**",
            inline=True
        )

        await interaction.channel.send(embed=result_embed)

        # Rewards
        if result['win']:
            rewards_embed = discord.Embed(
                title="🎁 Raid Rewards",
                description="Rewards have been distributed to all participants!",
                color=0xFFD700
            )
            rewards_text = ""

            for uid in lobby['members']:
                u = users.get(str(uid), {})
                # Shard
                s_name = self.boss['name']
                u.setdefault("fragments", {})
                u["fragments"][s_name] = u["fragments"].get(s_name, 0) + 2
                rewards_text += f"<@{uid}>: 💎 **2x {s_name} Shards**\n"

                # Weapon Chance
                if random.random() * 100 < self.boss['weapon_drop_rate']:
                    wid = self.boss['weapon_id']
                    u.setdefault("equipment", {})
                    u["equipment"][wid] = u["equipment"].get(wid, 0) + 1
                    rewards_text += f"✨ <@{uid}> **DROPPED {wid}!**\n"

            save(USERS_FILE, users)
            rewards_embed.description = rewards_text
            await interaction.channel.send(embed=rewards_embed)


class Raid(commands.Cog):
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
                "reset_tokens": 0
            }
        return users[uid]

    @commands.command(name="raid")
    async def raid_base(self, ctx, action: str = None, *, arg: str = ""):
        if action == "create":
            if not arg:
                embed = discord.Embed(
                    title="❌ No Boss Specified",
                    description="Usage: `ls raid create <boss_name>`\n\nExample: `ls raid create Gun Park`",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            bosses = load(BOSSES_FILE)
            # Fuzzy search
            boss = next((b for b in bosses.values()
                        if b['name'].lower() == arg.lower()), None)

            if not boss:
                embed = discord.Embed(
                    title="❌ Boss Not Found",
                    description=f"Could not find boss: **{arg}**\n\nCheck available bosses and try again.",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            users = load(USERS_FILE)
            user = self.ensure_user(users, str(ctx.author.id))
            save(USERS_FILE, users)
            tid = f"{boss['name'].lower().replace(' ', '_')}_ticket"

            if user.get("tickets", {}).get(tid, 0) < 1:
                embed = discord.Embed(
                    title="❌ Missing Ticket",
                    description=f"You need a **{boss['name']} Ticket** to create this raid!\n\nGet tickets from `ls pull` (2.5% chance).",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            # Consume
            user["tickets"][tid] -= 1
            save(USERS_FILE, users)

            # Code
            code = f"{boss['name'][:3].upper()}-{random.randint(1000, 9999)}"
            active_lobbies[code] = {"host": ctx.author.id,
                                    "boss": boss, "members": [ctx.author.id]}

            embed = discord.Embed(
                title=f"⚔️ Raid Lobby: {boss['name']}",
                description=f"**Lobby Code:** `{code}`\n\nUse the buttons below or type `ls party join {code}`",
                color=0xE67E22
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)

            if boss.get('image'):
                embed.set_thumbnail(url=boss['image'])

            # Boss stats preview
            boss_stats = boss.get('stats', {})
            if boss_stats:
                stats_text = f"⚔️ ATK: {boss_stats.get('attack', 'N/A')} | ❤️ HP: {boss_stats.get('health', 'N/A')}"
                embed.add_field(name="Boss Stats",
                                value=stats_text, inline=False)

            members_list = "\n".join(
                [f"• <@{uid}>" for uid in active_lobbies[code]['members']])
            embed.add_field(
                name=f"👥 Members (1/{boss['max_players']})",
                value=members_list,
                inline=False
            )

            embed.set_footer(text="Host can start the raid when ready!")

            await ctx.send(embed=embed, view=LobbyView(code, boss, boss['max_players']))

    @commands.command(name="party")
    async def party_join(self, ctx, action: str, code: str = None):
        if action == "join":
            if not code:
                embed = discord.Embed(
                    title="❌ No Code Provided",
                    description="Usage: `ls party join <code>`\n\nExample: `ls party join GUN-1234`",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            lobby = active_lobbies.get(code)
            if not lobby:
                embed = discord.Embed(
                    title="❌ Invalid Code",
                    description="This lobby code is invalid or has expired.\n\nLobbies expire after 10 minutes.",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            if len(lobby['members']) >= lobby['boss']['max_players']:
                embed = discord.Embed(
                    title="❌ Lobby Full",
                    description="This raid lobby is full!",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            if ctx.author.id in lobby['members']:
                embed = discord.Embed(
                    title="✅ Already Joined",
                    description=f"You're already in the **{lobby['boss']['name']}** raid!",
                    color=0x2ECC71
                )
                return await ctx.send(embed=embed)

            lobby['members'].append(ctx.author.id)

            embed = discord.Embed(
                title="✅ Joined Raid!",
                description=f"You've joined the **{lobby['boss']['name']}** raid!\n\n**Members:** {len(lobby['members'])}/{lobby['boss']['max_players']}",
                color=0x2ECC71
            )
            await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Raid(bot))
