import discord
from discord.ext import commands
from discord.ui import View, Select


class HelpCategorySelect(Select):
    """Single dropdown to choose help category (clean UI like finv)."""

    def __init__(self, ctx: commands.Context):
        self.ctx = ctx
        options = [
            discord.SelectOption(label="Gacha", value="gacha",
                                 description="Pulls and inventories", emoji="🎴"),
            discord.SelectOption(label="Combat", value="combat",
                                 description="PvP and teams", emoji="⚔️"),
            discord.SelectOption(label="Gang", value="gang",
                                 description="Gangs, XP, businesses", emoji="👥"),
            discord.SelectOption(label="Crew", value="crew",
                                 description="Crews and territories", emoji="🏛️"),
            discord.SelectOption(label="Economy", value="economy",
                                 description="Yen, chests, cooldowns", emoji="💰"),
            discord.SelectOption(
                label="Info", value="info", description="Profiles and leaderboards", emoji="ℹ️"),
            discord.SelectOption(
                label="Patreon", value="patreon", description="Supporter-only", emoji="💜"),
        ]
        super().__init__(
            placeholder="Select a command category…",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        # Only the original user can use this menu
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ This help menu isn't for you! Run `ls help` to open your own.", ephemeral=True)
            return

        value = self.values[0]

        def base_embed(title: str, desc: str) -> discord.Embed:
            embed = discord.Embed(
                title=title, description=desc, color=0x5865F2)
            embed.set_author(name="Command Help",
                             icon_url=self.ctx.author.display_avatar.url)
            embed.set_footer(
                text="Use ls <command> for more info on each command!")
            return embed

        if value == "gacha":
            embed = base_embed(
                "🎴 Gacha Commands",
                "Commands related to pulling characters and viewing your collection.",
            )
            embed.add_field(
                name="🎴 Gacha",
                value=(
                    "`ls pull` - Summon a character\n"
                    "`ls mp` - Mass pull all remaining pulls (Patreon only)\n"
                    "`ls inv` - View your collection\n"
                    "`ls ci` - Quick card inventory\n"
                    "`ls mci` - Mass card inventory"
                ),
                inline=False,
            )
        elif value == "combat":
            embed = base_embed(
                "⚔️ Combat Commands",
                "PvP battles and team management.",
            )
            embed.add_field(
                name="⚔️ Combat",
                value=(
                    "`ls fight` - Find a random player and start a PvP battle\n"
                    "`ls challenge @user` - Challenge a specific player\n"
                    "`ls team` - View your active battle team\n"
                    "`ls teamadd <card>` - Add a card to your team (max 4)\n"
                    "`ls teamremove <card>` - Remove a card from your team\n"
                    "`ls teamremoveall` - Clear your active team"
                ),
                inline=False,
            )
        elif value == "gang":
            embed = base_embed(
                "👥 Gang Commands",
                "Gang creation, management, XP and businesses.",
            )
            embed.add_field(
                name="👥 Gang",
                value=(
                    "`ls gang` - View your gang overview & XP bar\n"
                    "`ls gang create <name>` - Create a gang\n"
                    "`ls gang info` - Detailed gang info\n"
                    "`ls gang leave` - Leave your current gang (non-leader)\n"
                    "`ls gang disband` - Dismantle your gang (leader only)\n"
                    "`ls gang_add @user` - Add member to gang\n"
                    "`ls gang_remove @user` - Remove member from gang\n"
                    "`ls business_create <name>` - Create a gang business\n"
                    "`ls businessrework [name]` - Reroll a business's income (25k–60k, costs 100k yen)\n"
                    "`ls wts` - View White Tiger Job Center (defense agents)\n"
                    "`ls hire <agent>` - Hire a White Tiger agent using gang bank\n"
                    "`ls pay @user <amount>` - Pay a gang member from gang bank\n"
                    "`ls raid_log` - View recent raid logs\n"
                    "`ls approve <gang>` - Approve a gang to become a crew (Gun and Goo role)"
                ),
                inline=False,
            )
        elif value == "crew":
            embed = base_embed(
                "🏛️ Crew Commands",
                "Crews and shared territory map.",
            )
            embed.add_field(
                name="🏛️ Crew",
                value=(
                    "`ls crew create <name>` - Create crew (max 4 total)\n"
                    "`ls crew info` - View your crew info\n"
                    "`ls crew list` - List all crews\n"
                    "`ls crew_add @user` - Add member to crew\n"
                    "`ls crew_remove @user` - Remove member from crew\n"
                    "`ls map` - View gang & crew territory map"
                ),
                inline=False,
            )
        elif value == "economy":
            embed = base_embed(
                "💰 Economy Commands",
                "Currency, chests, and cooldowns.",
            )
            embed.add_field(
                name="💰 Economy",
                value=(
                    "`ls bal` - Check balance\n"
                    "`ls claim` - Daily rewards\n"
                    "`ls chest <type> [quantity]` - Open chest(s)\n"
                    "`ls reset` - Reset pulls (uses reset token)\n"
                    "`ls cd` - Check cooldowns"
                ),
                inline=False,
            )
        elif value == "info":
            embed = base_embed(
                "ℹ️ Info Commands",
                "Player info, inventories, and leaderboards.",
            )
            embed.add_field(
                name="ℹ️ Info",
                value=(
                    "`ls profile` - View profile\n"
                    "`ls inv` - View cards\n"
                    "`ls finv` - View fragments\n"
                    "`ls lb` - Leaderboard"
                ),
                inline=False,
            )
        else:  # patreon
            embed = base_embed(
                "💜 Patreon Commands",
                "Special commands available only to Patreon supporters.",
            )
            embed.add_field(
                name="💜 Patreon Only",
                value=(
                    "`ls mp` - Mass pull all remaining pulls at once\n"
                    "`ls mr` - Use a reset token and then mass pull (reset + mp in one command)\n"
                    "More Patreon-only features may be added in the future."
                ),
                inline=False,
            )

        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(View):
    """Simple view wrapping the category select."""

    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=180)
        self.add_item(HelpCategorySelect(ctx))


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", aliases=["commands", "h"])
    async def help(self, ctx):
        """Interactive help menu with category buttons"""
        embed = discord.Embed(
            title="📚 Lookism Bot Commands",
            description=(
                "Use the buttons below to browse command categories.\n\n"
                "• **Gacha** – Pulling and inventories\n"
                "• **Combat** – PvP and teams\n"
                "• **Gang / Crew** – Clans, businesses, and territories\n"
                "• **Economy** – Yen, chests, cooldowns\n"
                "• **Info** – Profiles and leaderboards\n"
                "• **Patreon** – Supporter-only commands"
            ),
            color=0x5865F2,
        )
        embed.set_author(name="Command Help",
                         icon_url=ctx.author.display_avatar.url)
        embed.set_footer(
            text="Use ls <command> for more details on any command.")

        view = HelpView(ctx)
        await ctx.send(embed=embed, view=view)


def setup(bot):
    bot.add_cog(Help(bot))
