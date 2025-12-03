import discord
import time
import random
from discord.ext import commands
from discord.ui import View, Button, button
from utils.database import load, save
from utils.game_math import regenerate_pulls
import config

USERS_FILE = "data/users.json"


class Economy(commands.Cog):
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
                "last_claim_ts": 0,
                "last_pull_regen_ts": int(time.time()),
                "reset_tokens": 0
            }
        return users[uid]

    @commands.command(name="reset", aliases=["resetpulls", "reset_pulls", "rpulls"])
    async def reset_pulls(self, ctx):
        """Reset your pulls using a reset token. Usage: ls reset"""
        users = load(USERS_FILE)
        uid = str(ctx.author.id)
        user = self.ensure_user(users, uid)

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

        current_pulls = user.get("pulls", 0)
        if current_pulls >= config.MAX_PULLS:
            embed = discord.Embed(
                title="❌ Already Full",
                description=(
                    f"Your pulls are already at maximum ({config.MAX_PULLS}/{config.MAX_PULLS})!\n\n"
                    "No need to reset."
                ),
                color=0xE74C3C,
            )
            embed.set_author(
                name=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.url,
            )
            return await ctx.send(embed=embed)

        # Consume one reset token and refill pulls
        user["pulls"] = config.MAX_PULLS
        user["reset_tokens"] = reset_tokens - 1
        user["last_pull_regen_ts"] = int(time.time())
        save(USERS_FILE, users)

        embed = discord.Embed(
            title="✅ Pulls Reset!",
            description=(
                f"Your pulls have been reset to **{config.MAX_PULLS}/{config.MAX_PULLS}**!\n\n"
                f"**Remaining Reset Tokens:** `{user['reset_tokens']}`"
            ),
            color=0x2ECC71,
        )
        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.send(embed=embed)

    @commands.command(name="bal", aliases=["balance", "money"])
    async def bal(self, ctx):
        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        save(USERS_FILE, users)  # Save if new user was created

        yen = user.get("yen", 0)
        tokens = user.get("reset_tokens", 0)
        pulls = user.get("pulls", 0)

        embed = discord.Embed(
            title="💰 Balance",
            color=0xFFD700
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        embed.add_field(
            name="💴 Yen",
            value=f"`{yen:,}`",
            inline=True
        )
        embed.add_field(
            name="🔄 Reset Tokens",
            value=f"`{tokens}`",
            inline=True
        )
        embed.add_field(
            name="🃏 Pulls",
            value=f"`{pulls}`/12",
            inline=True
        )

        # Show chests if any
        chests = user.get("chests", {})
        if chests:
            chest_text = "\n".join(
                [f"• {k}: `{v}`" for k, v in chests.items() if v > 0])
            if chest_text:
                embed.add_field(name="📦 Chests",
                                value=chest_text, inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="claim", aliases=["daily"])
    async def claim(self, ctx):
        users = load(USERS_FILE)
        uid = str(ctx.author.id)
        user = self.ensure_user(users, uid)

        now = int(time.time())
        last = user.get("last_claim_ts", 0)

        # Check cooldown (24 hours = 86400 seconds)
        if now - last < config.DAILY_COOLDOWN:
            rem = config.DAILY_COOLDOWN - (now - last)
            hours = rem // 3600
            minutes = (rem % 3600) // 60
            seconds = rem % 60

            embed = discord.Embed(
                title="⏳ Cooldown Active",
                description=f"**Time Remaining:** {hours}h {minutes}m {seconds}s\n\nCome back later to claim your daily rewards!",
                color=0xF39C12
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            embed.set_footer(text="Daily reset in 24 hours")
            return await ctx.send(embed=embed)

        # Calculate streak
        streak = user.get("claim_streak", 0)
        # If more than 2 days passed, reset streak
        if now - last > (config.DAILY_COOLDOWN * 2):
            streak = 0

        # Increment streak (cycles 1-5)
        streak = (streak % 5) + 1

        user.setdefault("chests", {})
        rw_msg = ""
        yen_gain = streak * 1000

        if streak == 1:
            user["chests"]["locker"] = user["chests"].get("locker", 0) + 1
            rw_msg = "🗄️ +1 Locker Chest"
        elif streak == 2:
            user["chests"]["locker"] = user["chests"].get("locker", 0) + 2
            rw_msg = "🗄️ +2 Locker Chests"
        elif streak == 5:
            user["chests"]["vvip"] = user["chests"].get("vvip", 0) + 1
            rw_msg = "💎 +1 VVIP Chest"
        else:
            rw_msg = "No bonus chest"

        user["yen"] = user.get("yen", 0) + yen_gain
        user["claim_streak"] = streak
        user["last_claim_ts"] = now  # Update timestamp
        save(USERS_FILE, users)

        embed = discord.Embed(
            title=f"📅 Day {streak} Claimed!",
            description=f"**Daily Rewards Collected**",
            color=0x2ECC71
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        embed.add_field(
            name="💰 Rewards",
            value=f"💴 **+{yen_gain:,}** Yen\n{rw_msg}",
            inline=False
        )
        embed.add_field(
            name="📊 Stats",
            value=f"Streak: `{streak}/5` days\nTotal Yen: `{user['yen']:,}`",
            inline=True
        )
        embed.set_footer(text="Come back tomorrow for more rewards!")
        await ctx.send(embed=embed)

    @commands.command(name="chest", aliases=["open"])
    async def chest(self, ctx, chest_type: str = None, quantity: int = 1):
        """Open chests! Usage: ls chest <chest_type> [quantity]"""
        if not chest_type:
            embed = discord.Embed(
                title="❌ No Chest Type",
                description="Please specify a chest type!\nUsage: `ls chest <chest_type> [quantity]`\n\nAvailable: `locker`, `vvip`\n\nExample: `ls chest locker 5`",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if quantity < 1:
            embed = discord.Embed(
                title="❌ Invalid Quantity",
                description="Quantity must be at least 1!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        users = load(USERS_FILE)
        uid = str(ctx.author.id)
        user = self.ensure_user(users, uid)
        chests = user.get("chests", {})
        available = chests.get(chest_type, 0)

        if available < 1:
            embed = discord.Embed(
                title="❌ No Chest Available",
                description=f"You don't have a **{chest_type}** chest.\n\nUse `ls claim` to get daily chests!",
                color=0xE74C3C
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        # Limit quantity to available
        quantity = min(quantity, available)

        # Calculate total rewards
        total_yen = 0
        total_pulls = 0

        for _ in range(quantity):
            # RNG rewards based on chest type
            if chest_type == "vvip":
                yen = random.randint(5000, 20000)
                bonus_pulls = random.choice([0, 0, 0, 1])  # 25% chance
            else:  # locker
                yen = random.randint(1000, 10000)
                bonus_pulls = 0

            total_yen += yen
            total_pulls += bonus_pulls

        # Consume chests
        user["chests"][chest_type] -= quantity
        user["yen"] = user.get("yen", 0) + total_yen
        if total_pulls > 0:
            user["pulls"] = min(12, user.get("pulls", 0) + total_pulls)

        save(USERS_FILE, users)

        embed = discord.Embed(
            title=f"📦 Opened {quantity}x {chest_type.upper()} Chest{'s' if quantity > 1 else ''}!",
            description=f"**Rewards Found:**",
            color=0xFFD700 if chest_type == "vvip" else 0x3498DB
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        embed.add_field(
            name="💰 Rewards",
            value=f"💴 **+{total_yen:,}** Yen" + (
                f"\n🃏 **+{total_pulls}** Pull{'s' if total_pulls > 1 else ''}!" if total_pulls > 0 else ""),
            inline=False
        )
        embed.add_field(
            name="💴 New Balance",
            value=f"`{user['yen']:,}` yen",
            inline=True
        )
        embed.add_field(
            name="📦 Remaining Chests",
            value=f"`{user['chests'].get(chest_type, 0)}` {chest_type}",
            inline=True
        )
        embed.set_footer(text="Keep collecting chests for better rewards!")
        await ctx.send(embed=embed)

    @commands.command(name="cd", aliases=["cooldown", "cooldowns"])
    async def cd(self, ctx):
        users = load(USERS_FILE)
        uid = str(ctx.author.id)
        user = self.ensure_user(users, uid)
        user = regenerate_pulls(user)
        save(USERS_FILE, users)

        now = int(time.time())
        pulls = user.get("pulls", 0)
        last_pull = user.get("last_pull_regen_ts", now)
        next_pull = max(0, config.PULL_REGEN_SECONDS - (now - last_pull))

        last_claim = user.get("last_claim_ts", 0)
        daily = max(0, config.DAILY_COOLDOWN - (now - last_claim))

        embed = discord.Embed(
            title="⏱️ Cooldowns",
            color=0x3498DB
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)

        # Pulls cooldown
        pull_hours = next_pull // 3600
        pull_mins = (next_pull % 3600) // 60
        pull_status = f"`{pulls}/12`" + \
            (f" (Next in: {pull_hours}h {pull_mins}m)" if next_pull >
             0 else " (Full!)")
        embed.add_field(
            name="🃏 Pulls",
            value=pull_status,
            inline=False
        )

        # Daily cooldown
        daily_hours = daily // 3600
        daily_mins = (daily % 3600) // 60
        daily_secs = daily % 60
        daily_status = f"{daily_hours}h {daily_mins}m {daily_secs}s" if daily > 0 else "✅ **Ready!**"
        embed.add_field(
            name="📅 Daily Claim",
            value=daily_status,
            inline=False
        )

        embed.set_footer(text="Check back later for refreshed cooldowns!")
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Economy(bot))
