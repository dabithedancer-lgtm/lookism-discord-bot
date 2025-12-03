import discord
import time
import json
import os
from discord.ext import commands
from discord.ui import View, Select
import config

USERS_FILE = "data/users.json"


def load(filename):
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return {}
    except:
        return {}


def save(data, filename):
    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving {filename}: {e}")


class PatreonTierSelect(Select):
    """Dropdown to select Patreon tier like help command"""

    def __init__(self, ctx: commands.Context):
        self.ctx = ctx
        options = [
            discord.SelectOption(label="Copy Tier", value="copy",
                                 description="$10/month - Perfect for starting supporters", emoji="🥉"),
            discord.SelectOption(label="UI Tier", value="ui",
                                 description="$25/month - Great value for dedicated players", emoji="🥈"),
            discord.SelectOption(label="TUI Tier", value="tui",
                                 description="$50/month - Ultimate experience for top supporters", emoji="🥇"),
            discord.SelectOption(label="How to Get", value="how",
                                 description="Learn how to become a patron", emoji="🔗"),
        ]
        super().__init__(
            placeholder="Select a Patreon tier or option…",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        # Only the original user can use this menu
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ This menu isn't for you! Run `ls patreon` to open your own.", ephemeral=True)
            return

        value = self.values[0]

        def base_embed(title: str, desc: str, color: int) -> discord.Embed:
            embed = discord.Embed(title=title, description=desc, color=color)
            embed.set_author(name="Patreon Support",
                             icon_url=self.ctx.author.display_avatar.url)
            return embed

        if value == "copy":
            embed = base_embed("🥉 Copy Tier - $10/month",
                               "**Perfect for starting supporters!**\n\n**Perks:**\n• 10% off on evolving\n• 1 extra roll (14 total pulls)\n• 10% more experience\n• 2k yen every bundle\n• -1 hour quest cooldown\n• Multiroll command\n• Bundle command (24h reset)\n\n**Ideal for:** Casual players who want a small boost", 0xC0C0C0)
            embed.set_footer(
                text="Upgrade anytime! Benefits stack with higher tiers.")
        elif value == "ui":
            embed = base_embed("🥈 UI Tier - $25/month",
                               "**Great value for dedicated players!**\n\n**Perks:**\n• 15% off on evolving\n• 2 extra rolls (17 total pulls)\n• 15% more experience\n• 3k yen every bundle\n• Locker loot crate\n• -1.5 hour quest cooldown\n• 1 ticket (random boss)\n• 5% vasco, 7% zack, 88% jace rates\n• Multiroll command\n\n**Ideal for:** Regular players who want significant benefits", 0x9B59B6)
            embed.set_footer(text="Best value tier! Includes all Copy perks.")
        elif value == "tui":
            embed = base_embed("🥇 TUI Tier - $50/month",
                               "**Ultimate experience for top supporters!**\n\n**Perks:**\n• 1 fragment discount per level\n• 20% off on evolving\n• 3 extra rolls (22 total pulls)\n• 20% more experience\n• 5k yen every bundle\n• Random crate (Locker loot/2nd tier)\n• -2 hour quest cooldown\n• 1 ticket each (vasco, jace, zack)\n• 10% vasco, 15% zack, 75% jace rates\n• Multiroll command\n• 1.5x aura points\n• 1.5x bounty points\n\n**Ideal for:** Dedicated players who want the best experience", 0xF1C40F)
            embed.set_footer(text="Premium tier! Includes all previous perks.")
        else:  # how
            embed = base_embed("🔗 How to Become a Patron",
                               "**Getting your Patreon perks is easy!**\n\n**Steps:**\n1. **Subscribe on Patreon** (link coming soon)\n2. **Get your Discord User ID** (right-click your profile → Copy ID)\n3. **Contact an admin** with your User ID\n4. **Receive your perks** instantly!\n\n**Or ask in #support channel for help!**\n\n**Current Admins:** Contact server moderators for assistance.", 0x3498DB)

        await interaction.response.edit_message(embed=embed, view=self.view)


class PatreonView(View):
    """Simple view wrapping the tier select"""

    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=180)
        self.add_item(PatreonTierSelect(ctx))


class OldPatreonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Copy Tier", style=discord.ButtonStyle.secondary, emoji="🥉")
    async def copy_tier(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🥉 Copy Tier - $10/month",
            color=0xC0C0C0
        )
        embed.description = """
**Perfect for starting supporters!**
                
**Perks:**
• 10% off on evolving
• 1 extra roll (14 total pulls)
• 10% more experience
• 2k yen every bundle
• -1 hour quest cooldown
• Multiroll command
• Bundle command (24h reset)
                
**Ideal for:** Casual players who want a small boost
"""
        embed.set_footer(
            text="Upgrade anytime! Benefits stack with higher tiers.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="UI Tier", style=discord.ButtonStyle.primary, emoji="🥈")
    async def ui_tier(self, button, interaction):
        embed = discord.Embed(
            title="🥈 UI Tier - $25/month",
            color=0x9B59B6
        )
        embed.description = """
**Great value for dedicated players!**

**Perks:**
• 15% off on evolving
• 2 extra rolls (17 total pulls)
• 15% more experience
• 3k yen every bundle
• Locker loot crate
• -1.5 hour quest cooldown
• 1 ticket (random boss)
• 5% vasco, 7% zack, 88% jace rates
• Multiroll command
                
**Ideal for:** Regular players who want significant benefits
"""
        embed.set_footer(
            text="Best value tier! Includes all Copy perks.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="TUI Tier", style=discord.ButtonStyle.success, emoji="🥇")
    async def tui_tier(self, button, interaction):
        embed = discord.Embed(
            title="🥇 TUI Tier - $50/month",
            color=0xF1C40F
        )
        embed.description = """
**Ultimate experience for top supporters!**

**Perks:**
• 1 fragment discount per level
• 20% off on evolving
• 3 extra rolls (22 total pulls)
• 20% more experience
• 5k yen every bundle
• Random crate (Locker loot/2nd tier)
• -2 hour quest cooldown
• 1 ticket each (vasco, jace, zack)
• 10% vasco, 15% zack, 75% jace rates
• Multiroll command
• 1.5x aura points
• 1.5x bounty points
                
**Ideal for:** Dedicated players who want the best experience
"""
        embed.set_footer(
            text="Premium tier! Includes all previous perks.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="How to Get", style=discord.ButtonStyle.secondary, emoji="🔗")
    async def how_to_get(self, button, interaction):
        embed = discord.Embed(
            title="🔗 How to Become a Patron",
            color=0x3498DB
        )
        embed.description = """
**Getting your Patreon perks is easy!**

**Steps:**
1. **Subscribe on Patreon** (link coming soon)
2. **Get your Discord User ID** (right-click your profile → Copy ID)
3. **Contact an admin** with your User ID
4. **Receive your perks** instantly!

**Or ask in #support channel for help!**

**Current Admins:** Contact server moderators for assistance.
"""
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="❌")
    async def close(self, button, interaction):
        await interaction.response.edit_message(view=None)


class Patreon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def check_patreon_expiration(self, users):
        """Check and remove expired Patreon subscriptions"""
        now = int(time.time())
        expired_users = []

        for uid, user_data in users.items():
            if "patreon" in user_data:
                if user_data["patreon"]["expires_at"] <= now:
                    expired_users.append(uid)
                    # Remove Patreon status
                    del user_data["patreon"]
                    user_data["max_pulls"] = 12  # Reset to default

        return expired_users

    @commands.command(name="patreon")
    async def patreon_info(self, ctx):
        """Interactive Patreon information command"""
        print(f"Patreon command called by {ctx.author.name}")

        # Check for expired subscriptions
        users = load(USERS_FILE)
        expired = self.check_patreon_expiration(users)
        if expired:
            save(users, USERS_FILE)

        # Main Patreon info embed
        embed = discord.Embed(
            title="👑 Patreon Support Tiers",
            description="**Your support means everything to us!** 🌟\n\nRunning and maintaining this bot takes countless hours of development, server costs, and dedication. Every Patreon subscription helps us keep the lights on, bring you exciting new features, and ensure the bot stays online 24/7 for everyone to enjoy. Your support directly fuels our passion to create amazing gaming experiences and allows us to continuously improve the bot with new cards, events, and content that makes your adventure even more epic!\n\n**All subscriptions last 30 days** and can be renewed anytime.",
            color=0xF1C40F
        )

        embed.add_field(
            name="🔗 How to Get Started",
            value="1. **Subscribe on Patreon** (link coming soon)\n2. **Get your Discord User ID** (right-click profile → Copy ID)\n3. **Contact an admin** with your User ID\n4. **Receive your perks** instantly!\n\nAsk in #support channel for help!",
            inline=False
        )

        embed.set_footer(
            text="Contact server moderators for assistance with Patreon setup.")
        embed.set_thumbnail(
            url="https://media.tenor.com/2RoDo8pZt6wAAAAC/black-clover-mobile-summon.gif")

        # Create and attach the interactive view
        view = PatreonView(ctx)
        await ctx.send(embed=embed, view=view)
        print(f"Patreon command completed for {ctx.author.name}")

    @commands.command(name="patreonadd", aliases=["pa"])
    @commands.has_permissions(administrator=True)
    async def patreon_add(self, ctx, user_id: int, tier: str = "1"):
        """Add Patreon role to a user. Usage: ls patreonadd <user_id> [tier]"""

        # Define Patreon tiers and their perks
        patreon_tiers = {
            "1": {
                "name": "Copy",
                "role_id": 1444532012424888454,
                "perks": ["10% off on evolving", "1 roll", "10% more exp", "2k yen every bundle", "-1 hour quest cd (st)", "Multiroll", "ls bundle command (24h reset)"]
            },
            "2": {
                "name": "UI",
                "role_id": 1444532053776535676,
                "perks": ["15% off on evolving", "2 rolls", "15% more exp", "3k yen every bundle", "locker loot crate", "-1.5 hour quest cd (st)", "1 ticket", "5% for vasco 7% for Zack and 88% for Jace", "Multiroll"]
            },
            "3": {
                "name": "TUI",
                "role_id": 1444532102338052216,
                "perks": ["1 frag discount per level", "20% off on evolving", "3 rolls", "20% more exp", "5k yen every bundle", "Random crate (Locker loot/2nd tier)", "-2 hour quest cd (st)", "1 ticket (vasco,Jace,Zack)", "10% vasco 15% Zack 75% Jace", "Multiroll", "1.5x aura points", "1.5x bounty points"]
            }
        }

        if tier not in patreon_tiers:
            await ctx.send("❌ Invalid tier! Use 1 (Copy), 2 (UI), or 3 (TUI)")
            return

        tier_info = patreon_tiers[tier]

        try:
            user = self.bot.get_user(user_id)
            if not user:
                await ctx.send(f"❌ User with ID {user_id} not found!")
                return

            # Store Patreon info in user data
            users = load(USERS_FILE)
            uid = str(user_id)

            if uid not in users:
                users[uid] = {}

            users[uid]["patreon"] = {
                "tier": tier,
                "name": tier_info["name"],
                "added_at": int(time.time()),
                # 30 days from now
                "expires_at": int(time.time()) + (30 * 24 * 60 * 60),
                "perks": tier_info["perks"]
            }

            # Apply perks based on tier
            if tier == "1":
                users[uid]["max_pulls"] = 14  # +2 extra pulls
                # -1 hour in seconds
                users[uid]["quest_cooldown_reduction"] = 3600
                users[uid]["exp_multiplier"] = 1.1  # 10% more exp
                users[uid]["yen_per_bundle"] = 2000
                users[uid]["multiroll"] = True
                users[uid]["bundle_command"] = True
                users[uid]["patreon_tier"] = 1
            elif tier == "2":
                users[uid]["max_pulls"] = 17  # +5 extra pulls
                # -1.5 hours in seconds
                users[uid]["quest_cooldown_reduction"] = 5400
                users[uid]["exp_multiplier"] = 1.15  # 15% more exp
                users[uid]["yen_per_bundle"] = 3000
                users[uid]["tickets"] = users[uid].get("tickets", {})
                users[uid]["tickets"]["default"] = users[uid]["tickets"].get(
                    "default", 0) + 1
                users[uid]["multiroll"] = True
                users[uid]["locker_loot_crate"] = True
                users[uid]["bounty_rates"] = {
                    "vasco": 0.05, "zack": 0.07, "jace": 0.88}
                users[uid]["patreon_tier"] = 2
            elif tier == "3":
                users[uid]["max_pulls"] = 22  # +10 extra pulls
                # -2 hours in seconds
                users[uid]["quest_cooldown_reduction"] = 7200
                users[uid]["exp_multiplier"] = 1.2  # 20% more exp
                users[uid]["yen_per_bundle"] = 5000
                users[uid]["tickets"] = users[uid].get("tickets", {})
                users[uid]["tickets"]["vasco"] = users[uid]["tickets"].get(
                    "vasco", 0) + 1
                users[uid]["tickets"]["jace"] = users[uid]["tickets"].get(
                    "jace", 0) + 1
                users[uid]["tickets"]["zack"] = users[uid]["tickets"].get(
                    "zack", 0) + 1
                users[uid]["multiroll"] = True
                users[uid]["random_crate"] = True
                users[uid]["bounty_rates"] = {
                    "vasco": 0.10, "zack": 0.15, "jace": 0.75}
                users[uid]["aura_multiplier"] = 1.5
                users[uid]["bounty_multiplier"] = 1.5
                users[uid]["patreon_tier"] = 3

            # Set current pulls to max_pulls when applying perks
            users[uid]["pulls"] = users[uid]["max_pulls"]

            # Save the updated user data
            save(users, USERS_FILE)

            # Reload the user data to ensure it's up to date
            users = load(USERS_FILE)

            # Try to assign Discord role if role_id is set
            guild = ctx.guild
            if guild and tier_info["role_id"]:
                member = guild.get_member(user_id)
                if member:
                    try:
                        await member.add_roles(guild.get_role(tier_info["role_id"]))
                        role_assigned = "✅ Discord role assigned!"
                    except:
                        role_assigned = "⚠️ Could not assign Discord role (check bot permissions)"
                else:
                    role_assigned = "⚠️ User not in server"
            else:
                role_assigned = "ℹ️ Set role_id in code to auto-assign Discord roles"

            embed = discord.Embed(
                title="🎉 Patreon Role Added!",
                description=f"**{user.mention}** is now a **{tier_info['name']}** tier patron!",
                color=0xF1C40F
            )
            embed.add_field(
                name="Tier", value=f"Tier {tier}: {tier_info['name']}", inline=True)
            embed.add_field(name="Perks", value="\n".join(
                f"• {perk}" for perk in tier_info['perks']), inline=False)
            embed.add_field(name="Status", value=role_assigned, inline=False)
            embed.set_thumbnail(url=user.display_avatar.url)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error adding Patreon role: {e}")

    @commands.command(name="patreonremove", aliases=["pr"])
    @commands.has_permissions(administrator=True)
    async def patreon_remove(self, ctx, user_id: int):
        """Remove Patreon status from a user. Usage: ls patreonremove <user_id>"""

        try:
            user = self.bot.get_user(user_id)
            if not user:
                await ctx.send(f"❌ User with ID {user_id} not found!")
                return

            # Remove Patreon info from user data
            users = load(USERS_FILE)
            uid = str(user_id)

            if uid in users and "patreon" in users[uid]:
                tier_name = users[uid]["patreon"]["name"]
                del users[uid]["patreon"]

                # Reset max pulls to default and update current pulls if needed
                users[uid]["max_pulls"] = 12
                if users[uid].get("pulls", 0) > 12:
                    users[uid]["pulls"] = 12
                    users[uid]["last_pull_regen_ts"] = int(time.time())

                save(users, USERS_FILE)

                # Reload the user data to ensure it's up to date
                users = load(USERS_FILE)

                embed = discord.Embed(
                    title="❌ Patreon Status Removed",
                    description=f"**{user.mention}** is no longer a patron (was {tier_name})",
                    color=0xE74C3C
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ {user.mention} is not a patron!")

        except Exception as e:
            await ctx.send(f"❌ Error removing Patreon status: {e}")

    @commands.command(name="patreonlist", aliases=["pl"])
    @commands.has_permissions(administrator=True)
    async def patreon_list(self, ctx):
        """List all current patrons with their tier and expiration"""

        users = load(USERS_FILE)
        patrons = []
        now = int(time.time())

        # First, check for expired patrons
        expired = self.check_patreon_expiration(users)
        if expired:
            save(users, USERS_FILE)
            print(f"Cleaned up {len(expired)} expired patrons")

        # Gather current patrons
        for uid, user_data in users.items():
            if "patreon" in user_data:
                try:
                    user = await self.bot.fetch_user(int(uid))
                    if user:
                        patrons.append({
                            "user": user,
                            "tier": user_data["patreon"]["tier"],
                            "name": user_data["patreon"].get("name", "Unknown"),
                            "expires_at": user_data["patreon"].get("expires_at", 0)
                        })
                except (discord.NotFound, discord.HTTPException):
                    continue

        if not patrons:
            await ctx.send("📭 No current patrons found!")
            return

        # Sort by tier (1,2,3) and then by username
        patrons_sorted = sorted(patrons, key=lambda x: (
            int(x['tier']), x['user'].name.lower()))

        embed = discord.Embed(
            title="👑 Current Patrons",
            description=f"Total active patrons: {len(patrons_sorted)}",
            color=0xF1C40F
        )

        # Group by tier for better organization
        tiers = {}
        for patron in patrons_sorted:
            tier = patron['tier']
            if tier not in tiers:
                tiers[tier] = []
            tiers[tier].append(patron)

        # Add fields for each tier
        for tier_num in sorted(tiers.keys(), key=int):
            tier_patrons = tiers[tier_num]
            tier_name = {
                '1': '🥉 Copy Tier',
                '2': '🥈 UI Tier',
                '3': '🥇 TUI Tier'
            }.get(tier_num, f'Tier {tier_num}')

            # Format patron list with mentions and expiration
            patron_list = []
            for patron in tier_patrons:
                days_left = (patron['expires_at'] - now) // (24 * 3600)
                if days_left > 0:
                    patron_list.append(
                        f"• {patron['user'].mention} ({patron['name']}) - {days_left} days left"
                    )
                else:
                    patron_list.append(
                        f"• {patron['user'].mention} ({patron['name']}) - Expired!"
                    )

            embed.add_field(
                name=f"{tier_name} ({len(tier_patrons)})",
                value="\n".join(patron_list) or "No patrons in this tier",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name="mp", aliases=["mass_pull", "masspull"])
    async def mass_pull(self, ctx):
        """Mass pull all remaining pulls at once (Patreon only)! Usage: ls mp"""
        # Check patreon status
        users = load(USERS_FILE)
        uid = str(ctx.author.id)
        if uid not in users or "patreon" not in users[uid]:
            embed = discord.Embed(
                title="❌ Patreon Only",
                description="This command is only available to **Patreon members**!\n\nUse `ls patreon` to learn more about supporting us!",
                color=0xE74C3C,
            )
            embed.set_author(
                name=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.url,
            )
            return await ctx.send(embed=embed)

        user = users[uid]
        amount = user.get("pulls", 0)
        if amount <= 0:
            max_pulls = user.get("max_pulls", 12)
            embed = discord.Embed(
                title="❌ Out of Pulls!",
                description=(
                    f"You have `{user.get('pulls', 0)}/{max_pulls}` pulls left. "
                    "Nothing to mass pull.\n\nUse `ls cd` to check cooldowns."
                ),
                color=0xE74C3C,
            )
            embed.set_author(
                name=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.url,
            )
            return await ctx.send(embed=embed)

        # Start mass pull
        loading_embed = discord.Embed(
            title="✨ Mass Pulling...",
            description=f"Pulling **{amount}** characters...",
            color=0x5865F2,
        )
        loading_embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url,
        )
        loading_embed.set_footer(text="This may take a moment...")
        msg = await ctx.send(embed=loading_embed)

        # Import needed modules for gacha logic
        import random
        import asyncio
        from utils.game_math import regenerate_pulls

        CARDS_FILE = "data/cards.json"
        RARITIES_FILE = "data/rarities.json"
        BOSSES_FILE = "data/bosses.json"
        EMOJI_FILE = "data/emoji.json"

        # Load data
        cards_dict = load(CARDS_FILE)
        rarities = load(RARITIES_FILE)
        bosses = load(BOSSES_FILE)

        if not cards_dict:
            embed = discord.Embed(
                title="❌ No Cards Available",
                description="Card database is empty!",
                color=0xE74C3C,
            )
            await msg.edit(embed=embed)
            return

        # Prepare card pool and weights
        cards_list = list(cards_dict.values())
        weights = []
        for card in cards_list:
            rarity_key = card.get("rarity", "C")
            rarity_info = rarities.get(rarity_key, {})
            weight = rarity_info.get("weight_multiplier", 5)
            weights.append(weight)

        # Load per-card emojis for fragments
        emojis = load(EMOJI_FILE) or {}

        # Aggregated results
        new_counts = {}      # card_name -> (count, rarity_emoji)
        shard_counts = {}    # card_name -> (count, card_emoji)
        tickets_gained = {}

        user["pulls"] -= amount

        for _ in range(amount):
            # Ticket chance (2.5%)
            if bosses and random.random() * 100 <= 2.5:
                total = sum(b.get("ticket_drop_rate", 0)
                            for b in bosses.values())
                if total > 0:
                    r = random.uniform(0, total)
                    curr = 0
                    for b in bosses.values():
                        curr += b.get("ticket_drop_rate", 0)
                        if r <= curr:
                            tid = f"{b.get('name', '').lower().replace(' ', '_')}_ticket"
                            tickets_gained[tid] = tickets_gained.get(
                                tid, 0) + 1
                            user.setdefault("tickets", {})
                            user["tickets"][tid] = user["tickets"].get(
                                tid, 0) + 1
                            break

            # Card pull
            chosen = random.choices(cards_list, weights=weights, k=1)[0]
            card_name = chosen.get("name", "Unknown")
            rarity_key = chosen.get("rarity", "C")
            rarity_info = rarities.get(rarity_key, {})
            rarity_emoji = rarity_info.get("emoji", "⭐")

            user.setdefault("cards", [])
            user.setdefault("unlocked", [])
            user.setdefault("fragments", {})

            if card_name not in user.get("unlocked", []):
                # New unlock
                user.setdefault("unlocked", []).append(card_name)
                user["cards"].append(
                    {
                        "name": card_name,
                        "rarity": rarity_key,
                        "level": 1,
                        "exp": 0,
                        "evo": 0,
                        "aura": 0,
                    }
                )
                count, _ = new_counts.get(card_name, (0, rarity_emoji))
                new_counts[card_name] = (count + 1, rarity_emoji)
            else:
                # Fragment (duplicate)
                user["fragments"][card_name] = user["fragments"].get(
                    card_name, 0) + 1
                card_emoji = emojis.get(card_name) or "🧩"
                count, _ = shard_counts.get(card_name, (0, card_emoji))
                shard_counts[card_name] = (count + 1, card_emoji)

        # Save user data
        users[uid] = user
        save(users, USERS_FILE)

        # Result embed
        result_embed = discord.Embed(
            title="✨ Mass Pull Complete!",
            description=f"Pulled **{amount}** characters!",
            color=0x2ECC71,
        )
        result_embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url,
        )

        # New cards section (rarity emoji)
        if new_counts:
            new_lines = []
            for name, (count, rarity_emoji) in list(new_counts.items())[:15]:
                if count == 1:
                    new_lines.append(f"{rarity_emoji} **{name}**")
                else:
                    new_lines.append(f"{rarity_emoji} **{name}** ×`{count}`")
            if len(new_counts) > 15:
                new_lines.append(f"*...and {len(new_counts) - 15} more*")
            result_embed.add_field(
                name="🎴 New Cards",
                value="\n".join(new_lines) or "None",
                inline=False,
            )

        # Fragment section (card emoji)
        if shard_counts:
            shard_lines = []
            for name, (count, card_emoji) in list(shard_counts.items())[:15]:
                shard_lines.append(
                    f"{card_emoji or '🧩'} **{name}** ×`{count}`")
            if len(shard_counts) > 15:
                shard_lines.append(f"*...and {len(shard_counts) - 15} more*")
            result_embed.add_field(
                name="💎 Fragments",
                value="\n".join(shard_lines) or "None",
                inline=False,
            )

        if tickets_gained:
            ticket_text = "\n".join(
                [f"• **{tid}:** `{count}`" for tid,
                    count in tickets_gained.items()]
            )
            result_embed.add_field(
                name="🎫 Tickets Gained",
                value=ticket_text,
                inline=False,
            )

        result_embed.add_field(
            name="🃏 Remaining Pulls",
            value=f"`{user['pulls']}/{user.get('max_pulls', 12)}`",
            inline=True,
        )

        result_embed.set_footer(text="Thanks for supporting us on Patreon! 💜")
        await msg.edit(embed=result_embed)

    @commands.command(name="mr")
    async def mass_reset_and_pull(self, ctx):
        """Patreon-only: use one reset token to refill pulls, then mass pull all at once."""
        # Check patreon status
        users = load(USERS_FILE)
        uid = str(ctx.author.id)
        if uid not in users or "patreon" not in users[uid]:
            embed = discord.Embed(
                title="❌ Patreon Only",
                description="This command is only available to **Patreon members**!\n\nUse `ls patreon` to learn more about supporting us!",
                color=0xE74C3C,
            )
            embed.set_author(
                name=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.url,
            )
            return await ctx.send(embed=embed)

        user = users[uid]

        # Check reset tokens
        reset_tokens = user.get("reset_tokens", 0)
        if reset_tokens < 1:
            embed = discord.Embed(
                title="❌ No Reset Tokens",
                description=(
                    "You don't have any reset tokens!\n\n"
                    "Ask an admin to give you reset tokens using `ls add reset <amount> @user`"
                ),
                color=0xE74C3C,
            )
            embed.set_author(
                name=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.url,
            )
            return await ctx.send(embed=embed)

        # Refill pulls using one reset token
        user["pulls"] = user.get("max_pulls", 12)
        user["reset_tokens"] = reset_tokens - 1
        user["last_pull_regen_ts"] = int(time.time())
        users[uid] = user
        save(users, USERS_FILE)

        # Now perform the same mass pull logic as mp
        amount = user.get("pulls", 0)
        if amount <= 0:
            max_pulls = user.get("max_pulls", 12)
            embed = discord.Embed(
                title="❌ Out of Pulls!",
                description=(
                    f"You have `{user.get('pulls', 0)}/{max_pulls}` pulls left. "
                    "Nothing to mass pull.\n\nUse `ls cd` to check cooldowns."
                ),
                color=0xE74C3C,
            )
            embed.set_author(
                name=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.url,
            )
            return await ctx.send(embed=embed)

        loading_embed = discord.Embed(
            title="✨ Reset + Mass Pulling...",
            description=(
                f"Used 1 reset token to refill pulls to **{user.get('max_pulls', 12)}/{user.get('max_pulls', 12)}**.\n"
                f"Now pulling **{amount}** characters..."
            ),
            color=0x5865F2,
        )
        loading_embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url,
        )
        loading_embed.set_footer(text="This may take a moment...")
        msg = await ctx.send(embed=loading_embed)

        # Import needed modules and load data
        import random
        import asyncio
        CARDS_FILE = "data/cards.json"
        RARITIES_FILE = "data/rarities.json"
        BOSSES_FILE = "data/bosses.json"
        EMOJI_FILE = "data/emoji.json"

        cards_dict = load(CARDS_FILE)
        rarities = load(RARITIES_FILE)
        bosses = load(BOSSES_FILE)

        if not cards_dict:
            embed = discord.Embed(
                title="❌ No Cards Available",
                description="Card database is empty!",
                color=0xE74C3C,
            )
            await msg.edit(embed=embed)
            return

        cards_list = list(cards_dict.values())
        weights = []
        for card in cards_list:
            rarity_key = card.get("rarity", "C")
            rarity_info = rarities.get(rarity_key, {})
            weight = rarity_info.get("weight_multiplier", 5)
            weights.append(weight)

        emojis = load(EMOJI_FILE) or {}

        new_counts = {}
        shard_counts = {}
        tickets_gained = {}

        user["pulls"] -= amount

        for _ in range(amount):
            if bosses and random.random() * 100 <= 2.5:
                total = sum(b.get("ticket_drop_rate", 0)
                            for b in bosses.values())
                if total > 0:
                    r = random.uniform(0, total)
                    curr = 0
                    for b in bosses.values():
                        curr += b.get("ticket_drop_rate", 0)
                        if r <= curr:
                            tid = f"{b.get('name', '').lower().replace(' ', '_')}_ticket"
                            tickets_gained[tid] = tickets_gained.get(
                                tid, 0) + 1
                            user.setdefault("tickets", {})
                            user["tickets"][tid] = user["tickets"].get(
                                tid, 0) + 1
                            break

            chosen = random.choices(cards_list, weights=weights, k=1)[0]
            card_name = chosen.get("name", "Unknown")
            rarity_key = chosen.get("rarity", "C")
            rarity_info = rarities.get(rarity_key, {})
            rarity_emoji = rarity_info.get("emoji", "⭐")

            user.setdefault("cards", [])
            user.setdefault("unlocked", [])
            user.setdefault("fragments", {})

            if card_name not in user.get("unlocked", []):
                user.setdefault("unlocked", []).append(card_name)
                user["cards"].append(
                    {
                        "name": card_name,
                        "rarity": rarity_key,
                        "level": 1,
                        "exp": 0,
                        "evo": 0,
                        "aura": 0,
                    }
                )
                count, _ = new_counts.get(card_name, (0, rarity_emoji))
                new_counts[card_name] = (count + 1, rarity_emoji)
            else:
                user["fragments"][card_name] = user["fragments"].get(
                    card_name, 0) + 1
                card_emoji = emojis.get(card_name) or "🧩"
                count, _ = shard_counts.get(card_name, (0, card_emoji))
                shard_counts[card_name] = (count + 1, card_emoji)

        users[uid] = user
        save(users, USERS_FILE)

        result_embed = discord.Embed(
            title="✨ Reset + Mass Pull Complete!",
            description=f"Pulled **{amount}** characters after resetting pulls!",
            color=0x2ECC71,
        )
        result_embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url,
        )

        if new_counts:
            new_lines = []
            for name, (count, rarity_emoji) in list(new_counts.items())[:15]:
                if count == 1:
                    new_lines.append(f"{rarity_emoji} **{name}**")
                else:
                    new_lines.append(f"{rarity_emoji} **{name}** ×`{count}`")
            if len(new_counts) > 15:
                new_lines.append(f"*...and {len(new_counts) - 15} more*")
            result_embed.add_field(
                name="🎴 New Cards",
                value="\n".join(new_lines) or "None",
                inline=False,
            )

        if shard_counts:
            shard_lines = []
            for name, (count, card_emoji) in list(shard_counts.items())[:15]:
                shard_lines.append(
                    f"{card_emoji or '🧩'} **{name}** ×`{count}`")
            if len(shard_counts) > 15:
                shard_lines.append(f"*...and {len(shard_counts) - 15} more*")
            result_embed.add_field(
                name="💎 Fragments",
                value="\n".join(shard_lines) or "None",
                inline=False,
            )

        if tickets_gained:
            ticket_text = "\n".join(
                [f"• **{tid}:** `{count}`" for tid,
                    count in tickets_gained.items()]
            )
            result_embed.add_field(
                name="🎫 Tickets Gained",
                value=ticket_text,
                inline=False,
            )

        result_embed.add_field(
            name="🃏 Remaining Pulls",
            value=f"`{user['pulls']}/{user.get('max_pulls', 12)}`",
            inline=True,
        )

        result_embed.set_footer(text="Thanks for supporting us on Patreon! 💜")
        await msg.edit(embed=result_embed)


async def setup(bot):
    print("Setting up Patreon cog...")
    await bot.add_cog(Patreon(bot))
    print("Patreon cog loaded successfully!")
