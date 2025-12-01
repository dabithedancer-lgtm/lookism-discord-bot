import discord
from discord.ext import commands
from utils.database import load, save
import config
from difflib import get_close_matches

USERS_FILE = "data/users.json"
CARDS_FILE = "data/cards.json"


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return ctx.author.id in config.ADMINS

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
                "reset_tokens": 0
            }
        return users[uid]

    def find_card(self, cards_db, search_name: str):
        """Fuzzy find a card by name from cards.json.

        Tries exact match, then substring, then fuzzy match using difflib.
        Returns the card dict or None.
        """
        if not search_name:
            return None

        search = search_name.lower().strip()
        if not search:
            return None

        # 1. Exact (case-insensitive)
        for card in cards_db.values():
            if card.get("name", "").lower() == search:
                return card

        # 2. Substring contains
        partial_matches = [
            card for card in cards_db.values()
            if search in card.get("name", "").lower()
        ]
        if len(partial_matches) == 1:
            return partial_matches[0]
        if len(partial_matches) > 1:
            # Pick the closest by fuzzy score
            names = [c.get("name", "") for c in partial_matches]
            best = get_close_matches(search_name, names, n=1, cutoff=0.0)
            if best:
                return next((c for c in partial_matches if c.get("name") == best[0]), partial_matches[0])

        # 3. Fuzzy across all names
        all_names = [c.get("name", "") for c in cards_db.values()]
        best = get_close_matches(search_name, all_names, n=1, cutoff=0.6)
        if best:
            return next((c for c in cards_db.values() if c.get("name") == best[0]), None)

        return None

    @commands.command(name="add")
    async def add(self, ctx, type: str, amount: int, member: discord.Member = None):
        """Add items to a user. Usage: ls add <type> <amount> [@user]"""
        if member is None:
            member = ctx.author

        users = load(USERS_FILE)
        uid = str(member.id)
        user = self.ensure_user(users, uid)

        embed = discord.Embed(color=0x2ECC71)
        embed.set_author(
            name=f"Admin: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        if type == "yen":
            user["yen"] = user.get("yen", 0) + amount
            msg = f"Added ¥{amount:,} to {member.display_name}"
            embed.title = "✅ Yen Added"
            embed.description = f"**{member.mention}** received **{amount:,}** yen"
            embed.add_field(name="💰 New Balance",
                            value=f"`{user['yen']:,}` yen", inline=True)

        elif type == "ticket":
            ticket_id = ctx.message.content.split(
            )[-1] if len(ctx.message.content.split()) > 4 else None
            if not ticket_id or ticket_id.startswith("<@"):
                return await ctx.send("❌ Specify ticket ID. Usage: `ls add ticket <amount> @user <ticket_id>`")
            user.setdefault("tickets", {})
            user["tickets"][ticket_id] = user["tickets"].get(
                ticket_id, 0) + amount
            msg = f"Added {amount}x {ticket_id} to {member.display_name}"
            embed.title = "✅ Ticket Added"
            embed.description = f"**{member.mention}** received **{amount}x {ticket_id}**"

        elif type == "item" or type == "equipment":
            item_id = ctx.message.content.split(
            )[-1] if len(ctx.message.content.split()) > 4 else None
            if not item_id or item_id.startswith("<@"):
                return await ctx.send("❌ Specify item ID. Usage: `ls add item <amount> @user <item_id>`")
            user.setdefault("equipment", {})
            user["equipment"][item_id] = user["equipment"].get(
                item_id, 0) + amount
            msg = f"Added {amount}x {item_id} to {member.display_name}"
            embed.title = "✅ Item Added"
            embed.description = f"**{member.mention}** received **{amount}x {item_id}**"

        elif type == "pulls" or type == "pull":
            user["pulls"] = min(12, user.get("pulls", 0) + amount)
            msg = f"Added {amount} pulls to {member.display_name}"
            embed.title = "✅ Pulls Added"
            embed.description = f"**{member.mention}** received **{amount}** pulls"
            embed.add_field(name="🃏 Total Pulls",
                            value=f"`{user['pulls']}/12`", inline=True)

        elif type == "reset" or type == "reset_token":
            user.setdefault("reset_tokens", 0)
            user["reset_tokens"] = user.get("reset_tokens", 0) + amount
            embed.title = "✅ Reset Tokens Added"
            embed.description = f"**{member.mention}** received **{amount}** reset token(s)"
            embed.add_field(name="🔄 Total Reset Tokens",
                            value=f"`{user['reset_tokens']}`", inline=True)

        elif type == "card":
            # Everything after the amount and optional member mention is treated as card search text
            parts = ctx.message.content.split()
            # ls add card <amount> [@user] <card name...>
            # Find index of type and amount, everything after member (if any) is name
            try:
                type_index = parts.index(type)
            except ValueError:
                type_index = 2
            name_parts = parts[type_index + 2:]
            if member is not None and member.mention in parts:
                # Skip the first occurrence of the mention
                mention_index = parts.index(member.mention)
                name_parts = parts[mention_index + 1:]
            card_name = " ".join(name_parts).strip()
            if not card_name:
                return await ctx.send("❌ Specify card name. Usage: `ls add card <amount> @user <card_name>`")

            cards_db = load(CARDS_FILE)
            card_data = self.find_card(cards_db, card_name)
            if not card_data:
                return await ctx.send(f"❌ Card '{card_name}' not found in database!")

            user.setdefault("cards", [])
            user.setdefault("unlocked", [])

            for _ in range(amount):
                if card_data["name"] not in user.get("unlocked", []):
                    user.setdefault("unlocked", []).append(card_data["name"])
                user["cards"].append({
                    "name": card_data["name"],
                    "rarity": card_data["rarity"],
                    "level": 1,
                    "exp": 0,
                    "evo": 0,
                    "aura": 0
                })

            msg = f"Added {amount}x {card_data['name']} to {member.display_name}"
            embed.title = "✅ Card Added"
            embed.description = f"**{member.mention}** received **{amount}x {card_data['name']}**"

        elif type in ["frag", "frags", "fragment", "fragments", "shard", "shards"]:
            # Add character fragments by card name (fuzzy)
            parts = ctx.message.content.split()
            try:
                type_index = parts.index(type)
            except ValueError:
                type_index = 2
            name_parts = parts[type_index + 2:]
            if member is not None and member.mention in parts:
                mention_index = parts.index(member.mention)
                name_parts = parts[mention_index + 1:]
            card_name = " ".join(name_parts).strip()
            if not card_name:
                return await ctx.send("❌ Specify card name. Usage: `ls add frag <amount> @user <card_name>`")

            cards_db = load(CARDS_FILE)
            card_data = self.find_card(cards_db, card_name)
            if not card_data:
                return await ctx.send(f"❌ Card '{card_name}' not found in database!")

            real_name = card_data["name"]
            user.setdefault("fragments", {})
            user["fragments"][real_name] = user["fragments"].get(
                real_name, 0) + amount

            msg = f"Added {amount} fragments of {real_name} to {member.display_name}"
            embed.title = "✅ Fragments Added"
            embed.description = f"**{member.mention}** received **{amount}x {real_name} fragments**"

        elif type in ["chest", "chests"]:
            # Generic chest ID
            chest_id = ctx.message.content.split(
            )[-1] if len(ctx.message.content.split()) > 4 else None
            if not chest_id or chest_id.startswith("<@"):
                return await ctx.send("❌ Specify chest ID. Usage: `ls add chest <amount> @user <chest_id>`")
            user.setdefault("chests", {})
            user["chests"][chest_id] = user["chests"].get(chest_id, 0) + amount
            msg = f"Added {amount}x {chest_id} chest(s) to {member.display_name}"
            embed.title = "✅ Chests Added"
            embed.description = f"**{member.mention}** received **{amount}x {chest_id}**"

        else:
            embed = discord.Embed(
                title="❌ Invalid Type",
                description="Available types: `yen`, `ticket`, `item`, `pulls`, `reset`, `card`, `frag`, `chest`",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        save(USERS_FILE, users)
        await ctx.send(embed=embed)

    @commands.command(name="remove", aliases=["rem"])
    async def remove(self, ctx, type: str, amount: int, member: discord.Member = None):
        """Remove items from a user. Usage: ls remove <type> <amount> [@user]"""
        if member is None:
            member = ctx.author

        users = load(USERS_FILE)
        uid = str(member.id)
        if uid not in users:
            return await ctx.send(f"❌ {member.display_name} has no data.")

        user = users[uid]
        embed = discord.Embed(color=0xE74C3C)
        embed.set_author(
            name=f"Admin: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        if type == "yen":
            user["yen"] = max(0, user.get("yen", 0) - amount)
            embed.title = "✅ Yen Removed"
            embed.description = f"**{amount:,}** yen removed from **{member.mention}**"
            embed.add_field(name="💰 New Balance",
                            value=f"`{user['yen']:,}` yen", inline=True)
        elif type == "pulls" or type == "pull":
            user["pulls"] = max(0, user.get("pulls", 0) - amount)
            embed.title = "✅ Pulls Removed"
            embed.description = f"**{amount}** pulls removed from **{member.mention}**"
        elif type == "reset" or type == "reset_token":
            user["reset_tokens"] = max(0, user.get("reset_tokens", 0) - amount)
            embed.title = "✅ Reset Tokens Removed"
            embed.description = f"**{amount}** reset token(s) removed from **{member.mention}**"
        elif type == "ticket":
            ticket_id = ctx.message.content.split(
            )[-1] if len(ctx.message.content.split()) > 4 else None
            if not ticket_id or ticket_id.startswith("<@"):
                return await ctx.send("❌ Specify ticket ID. Usage: `ls remove ticket <amount> @user <ticket_id>`")
            user.setdefault("tickets", {})
            current = user["tickets"].get(ticket_id, 0)
            user["tickets"][ticket_id] = max(0, current - amount)
            embed.title = "✅ Ticket Removed"
            embed.description = f"**{amount}x {ticket_id}** removed from **{member.mention}**"
        elif type == "item" or type == "equipment":
            item_id = ctx.message.content.split(
            )[-1] if len(ctx.message.content.split()) > 4 else None
            if not item_id or item_id.startswith("<@"):
                return await ctx.send("❌ Specify item ID. Usage: `ls remove item <amount> @user <item_id>`")
            user.setdefault("equipment", {})
            current = user["equipment"].get(item_id, 0)
            user["equipment"][item_id] = max(0, current - amount)
            embed.title = "✅ Item Removed"
            embed.description = f"**{amount}x {item_id}** removed from **{member.mention}**"
        elif type in ["frag", "frags", "fragment", "fragments", "shard", "shards"]:
            parts = ctx.message.content.split()
            try:
                type_index = parts.index(type)
            except ValueError:
                type_index = 2
            name_parts = parts[type_index + 2:]
            if member is not None and member.mention in parts:
                mention_index = parts.index(member.mention)
                name_parts = parts[mention_index + 1:]
            card_name = " ".join(name_parts).strip()
            if not card_name:
                return await ctx.send("❌ Specify card name. Usage: `ls remove frag <amount> @user <card_name>`")

            cards_db = load(CARDS_FILE)
            card_data = self.find_card(cards_db, card_name)
            if not card_data:
                return await ctx.send(f"❌ Card '{card_name}' not found in database!")

            real_name = card_data["name"]
            user.setdefault("fragments", {})
            current = user["fragments"].get(real_name, 0)
            user["fragments"][real_name] = max(0, current - amount)

            embed.title = "✅ Fragments Removed"
            embed.description = f"**{amount}x {real_name} fragments** removed from **{member.mention}**"
        elif type in ["chest", "chests"]:
            chest_id = ctx.message.content.split(
            )[-1] if len(ctx.message.content.split()) > 4 else None
            if not chest_id or chest_id.startswith("<@"):
                return await ctx.send("❌ Specify chest ID. Usage: `ls remove chest <amount> @user <chest_id>`")
            user.setdefault("chests", {})
            current = user["chests"].get(chest_id, 0)
            user["chests"][chest_id] = max(0, current - amount)
            embed.title = "✅ Chests Removed"
            embed.description = f"**{amount}x {chest_id}** removed from **{member.mention}**"
        else:
            return await ctx.send("❌ Invalid type. Use: yen, pulls, reset, ticket, item, frag, chest")

        save(USERS_FILE, users)
        await ctx.send(embed=embed)

    @commands.command(name="set")
    async def set_value(self, ctx, type: str, value: int, member: discord.Member = None):
        """Set a value for a user. Usage: ls set <type> <value> [@user]"""
        if member is None:
            member = ctx.author

        users = load(USERS_FILE)
        uid = str(member.id)
        user = self.ensure_user(users, uid)

        embed = discord.Embed(color=0x3498DB)
        embed.set_author(
            name=f"Admin: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        if type == "yen":
            user["yen"] = max(0, value)
            embed.title = "✅ Yen Set"
            embed.description = f"**{member.mention}**'s yen set to **{value:,}**"
        elif type == "pulls" or type == "pull":
            user["pulls"] = max(0, min(12, value))
            embed.title = "✅ Pulls Set"
            embed.description = f"**{member.mention}**'s pulls set to **{value}/12**"
        elif type == "wins":
            user["wins"] = max(0, value)
            embed.title = "✅ Wins Set"
            embed.description = f"**{member.mention}**'s wins set to **{value}**"
        elif type == "streak":
            user["streak"] = max(0, value)
            embed.title = "✅ Streak Set"
            embed.description = f"**{member.mention}**'s streak set to **{value}**"
        elif type == "reset" or type == "reset_token":
            user.setdefault("reset_tokens", 0)
            user["reset_tokens"] = max(0, value)
            embed.title = "✅ Reset Tokens Set"
            embed.description = f"**{member.mention}**'s reset tokens set to **{value}**"
        else:
            return await ctx.send("❌ Invalid type. Use: yen, pulls, wins, streak, reset")

        save(USERS_FILE, users)
        await ctx.send(embed=embed)

    @commands.command(name="wipe")
    async def wipe(self, ctx, member: discord.Member = None):
        """Wipe a user's data. Usage: ls wipe [@user]"""
        if member is None:
            member = ctx.author

        users = load(USERS_FILE)
        uid = str(member.id)

        if uid in users:
            del users[uid]
            save(USERS_FILE, users)
            embed = discord.Embed(
                title="🗑️ Data Wiped",
                description=f"All data for **{member.mention}** has been wiped.",
                color=0xE74C3C
            )
            embed.set_author(
                name=f"Admin: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ {member.display_name} has no data.")

    @commands.command(name="adminreset", aliases=["areset"])
    async def admin_reset(self, ctx, type: str = None, member: discord.Member = None):
        """Admin-only reset for specific data. Usage: ls adminreset <type> [@user]"""
        # If type is missing, show a friendly usage message instead of raising
        if type is None:
            return await ctx.send("❌ Usage: `ls adminreset <cooldown|pulls|streak> [@user]`")

        if member is None:
            member = ctx.author

        users = load(USERS_FILE)
        uid = str(member.id)
        if uid not in users:
            return await ctx.send(f"❌ {member.display_name} has no data.")

        user = users[uid]
        embed = discord.Embed(color=0xF39C12)
        embed.set_author(
            name=f"Admin: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        if type == "cooldown" or type == "claim":
            user["last_claim_ts"] = 0
            embed.title = "✅ Cooldown Reset"
            embed.description = f"**{member.mention}**'s daily claim cooldown has been reset"
        elif type == "pulls":
            user["last_pull_regen_ts"] = 0
            embed.title = "✅ Pull Cooldown Reset"
            embed.description = f"**{member.mention}**'s pull cooldown has been reset"
        elif type == "streak":
            user["streak"] = 0
            embed.title = "✅ Streak Reset"
            embed.description = f"**{member.mention}**'s win streak has been reset"
        else:
            return await ctx.send("❌ Invalid type. Use: cooldown, pulls, streak")

        save(USERS_FILE, users)
        await ctx.send(embed=embed)

    @commands.command(name="give")
    async def give(self, ctx, member: discord.Member, type: str, amount: int):
        """Give items to a user (alias for add). Usage: ls give @user <type> <amount>"""
        await self.add(ctx, type, amount, member)

    @commands.command(name="userinfo", aliases=["uinfo"])
    async def userinfo(self, ctx, member: discord.Member = None):
        """View a user's data. Usage: ls userinfo [@user]"""
        if member is None:
            member = ctx.author

        users = load(USERS_FILE)
        uid = str(member.id)
        user = users.get(uid, {})

        if not user:
            return await ctx.send(f"❌ {member.display_name} has no data.")

        embed = discord.Embed(
            title=f"👤 {member.display_name}'s Data",
            color=0x5865F2
        )
        embed.set_author(
            name=f"Admin: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name="💴 Yen", value=f"`{user.get('yen', 0):,}`", inline=True)
        embed.add_field(
            name="🃏 Pulls", value=f"`{user.get('pulls', 0)}/12`", inline=True)
        embed.add_field(name="🔄 Reset Tokens",
                        value=f"`{user.get('reset_tokens', 0)}`", inline=True)
        embed.add_field(
            name="🎴 Cards", value=f"`{len(user.get('cards', []))}`", inline=True)
        embed.add_field(
            name="🏆 Wins", value=f"`{user.get('wins', 0)}`", inline=True)
        embed.add_field(name="🔥 Streak",
                        value=f"`{user.get('streak', 0)}`", inline=True)
        embed.add_field(
            name="📦 Chests", value=f"`{sum(user.get('chests', {}).values())}`", inline=True)

        await ctx.send(embed=embed)

    @commands.command(name="adminhelp", aliases=["ahelp"])
    async def admin_help(self, ctx):
        """Show admin-only command help. Usage: ls adminhelp"""
        embed = discord.Embed(
            title="🛠️ Admin Command Help",
            description=(
                "These commands are **admin-only** (checked via `config.ADMINS`).\n"
                "Use them carefully, they directly modify player data."
            ),
            color=0xE67E22
        )
        embed.set_author(
            name=f"Admin: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        embed.add_field(
            name="➕ ls add",
            value=(
                "`ls add <type> <amount> [@user] ...`\n"
                "Types: `yen`, `pulls`, `reset`, `ticket`, `item`, `card`, `frag`, `chest`\n"
                "Examples:\n"
                "• `ls add yen 100000 @user`\n"
                "• `ls add card 1 @user Mira Kim` (fuzzy card search)\n"
                "• `ls add frag 10 @user Mira` (fragments by card name)\n"
                "• `ls add ticket 3 @user boss_ticket`\n"
                "• `ls add chest 2 @user raid_chest_1`"
            ),
            inline=False
        )

        embed.add_field(
            name="➖ ls remove / ls rem",
            value=(
                "`ls remove <type> <amount> [@user] ...`\n"
                "Types: `yen`, `pulls`, `reset`, `ticket`, `item`, `frag`, `chest`\n"
                "Examples:\n"
                "• `ls remove yen 50000 @user`\n"
                "• `ls rem frag 5 @user Mira`\n"
                "• `ls rem ticket 1 @user boss_ticket`"
            ),
            inline=False
        )

        embed.add_field(
            name="⚙️ ls set",
            value=(
                "`ls set <type> <value> [@user]`\n"
                "Types: `yen`, `pulls`, `wins`, `streak`, `reset`\n"
                "Examples:\n"
                "• `ls set yen 250000 @user`\n"
                "• `ls set pulls 12 @user`\n"
                "• `ls set wins 50 @user`"
            ),
            inline=False
        )

        embed.add_field(
            name="🧹 ls wipe",
            value="`ls wipe [@user]` – Delete ALL stored data for a user.",
            inline=False
        )

        embed.add_field(
            name="🔄 ls reset",
            value=(
                "`ls reset <type> [@user]`\n"
                "Types: `cooldown`, `pulls`, `streak`\n"
                "Examples:\n"
                "• `ls reset cooldown @user`\n"
                "• `ls reset pulls @user`"
            ),
            inline=False
        )

        embed.add_field(
            name="👤 ls userinfo / ls uinfo",
            value="`ls userinfo [@user]` – Show a quick overview of a user's stored data.",
            inline=False
        )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
