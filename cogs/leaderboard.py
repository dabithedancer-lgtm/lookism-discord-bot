import discord
from discord.ext import commands
from utils.database import load

USERS_FILE = "data/users.json"


class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="lb", aliases=["leaderboard", "top"])
    async def lb(self, ctx):
        users = load(USERS_FILE)
        # Filter out users with no yen data and sort
        valid_users = [(uid, u) for uid, u in users.items()
                       if isinstance(u, dict) and 'yen' in u]
        sorted_users = sorted(
            valid_users, key=lambda x: x[1].get('yen', 0), reverse=True)

        if not sorted_users:
            embed = discord.Embed(
                title="🏆 Leaderboard",
                description="No players found!",
                color=0xFFD700
            )
            return await ctx.send(embed=embed)

        desc = ""
        medals = ["🥇", "🥈", "🥉"]

        for i, (uid, u) in enumerate(sorted_users[:10]):
            medal = medals[i] if i < 3 else f"**{i+1}.**"
            yen = u.get('yen', 0)
            desc += f"{medal} <@{uid}> - 💴 `{yen:,}` yen\n"

        embed = discord.Embed(
            title="🏆 Global Rankings",
            description=desc or "No players yet!",
            color=0xFFD700
        )
        embed.set_author(name="Top 10 Richest Players",
                         icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text="Compete to reach the top!")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
