import discord
import time
from discord.ext import commands
from utils.database import load, save
import config

USERS_FILE = "data/users.json"


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

        # Check for expired subscriptions
        users = load(USERS_FILE)
        expired = self.check_patreon_expiration(users)
        if expired:
            save(USERS_FILE, users)

        # Create interactive Patreon info view
        class PatreonView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)

            @discord.ui.button(label="Copy Tier", style=discord.ButtonStyle.secondary, emoji="🥉")
            async def copy_tier(self, interaction: discord.Interaction, button: discord.ui.Button):
                embed = discord.Embed(
                    title="🥉 Copy Tier - $5/month",
                    color=0xC0C0C0
                )
                embed.description = """
**Perfect for starting supporters!**
                
**Perks:**
• Placeholder perk 1
• Placeholder perk 2
• Placeholder perk 3
                
**Ideal for:** Casual players who want a small boost
"""
                embed.set_footer(
                    text="Upgrade anytime! Benefits stack with higher tiers.")
                await interaction.response.edit_message(embed=embed, view=self)

            @discord.ui.button(label="UI Tier", style=discord.ButtonStyle.primary, emoji="🥈")
            async def ui_tier(self, interaction: discord.Interaction, button: discord.ui.Button):
                embed = discord.Embed(
                    title="🥈 UI Tier - $10/month",
                    color=0x9B59B6
                )
                embed.description = """
**Great value for dedicated players!**

**Perks:**
• Placeholder perk A
• Placeholder perk B
• Placeholder perk C
• Placeholder perk D
                
**Ideal for:** Regular players who want significant benefits
"""
                embed.set_footer(
                    text="Best value tier! Includes all Copy perks.")
                await interaction.response.edit_message(embed=embed, view=self)

            @discord.ui.button(label="TUI Tier", style=discord.ButtonStyle.success, emoji="🥇")
            async def tui_tier(self, interaction: discord.Interaction, button: discord.ui.Button):
                embed = discord.Embed(
                    title="🥇 TUI Tier - $20/month",
                    color=0xF1C40F
                )
                embed.description = """
**Ultimate experience for top supporters!**

**Perks:**
• Placeholder perk Alpha
• Placeholder perk Beta
• Placeholder perk Gamma
• Placeholder perk Delta
• Placeholder perk Epsilon
                
**Ideal for:** Dedicated players who want the best experience
"""
                embed.set_footer(
                    text="Premium tier! Includes all previous perks.")
                await interaction.response.edit_message(embed=embed, view=self)

            @discord.ui.button(label="How to Get", style=discord.ButtonStyle.link, emoji="🔗")
            async def how_to_get(self, interaction: discord.Interaction, button: discord.ui.Button):
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
                await interaction.response.edit_message(embed=embed, view=self)

            @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="❌")
            async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.edit_message(view=None)

        # Main Patreon info embed
        embed = discord.Embed(
            title="👑 Patreon Support Tiers",
            description="Support our server and get amazing benefits!\n\n**All subscriptions last 30 days** and can be renewed anytime.",
            color=0xF1C40F
        )

        embed.add_field(
            name="🎯 Why Support Us?",
            value="• Help keep the bot running 24/7\n• Get exclusive perks and benefits\n• Support development of new features\n• Join an amazing community",
            inline=False
        )

        embed.add_field(
            name="⏰ Subscription Details",
            value="• **Duration:** 30 days\n• **Auto-renewal:** Manual (contact admin)\n• **Upgrades:** Pro-rated credit available\n• **Downgrades:** Takes effect next cycle",
            inline=False
        )

        embed.set_footer(text="Click the buttons below to explore each tier!")
        embed.set_thumbnail(
            url="https://media.tenor.com/2RoDo8pZt6wAAAAC/black-clover-mobile-summon.gif")

        await ctx.send(embed=embed, view=PatreonView())

    @commands.command(name="patreonadd", aliases=["pa"])
    @commands.has_permissions(administrator=True)
    async def patreon_add(self, ctx, user_id: int, tier: str = "1"):
        """Add Patreon role to a user. Usage: ls patreonadd <user_id> [tier]"""

        # Define Patreon tiers and their perks
        patreon_tiers = {
            "1": {
                "name": "Copy",
                "role_id": None,  # Set this to your actual Discord role ID
                "perks": ["Placeholder perk 1", "Placeholder perk 2", "Placeholder perk 3"]
            },
            "2": {
                "name": "UI",
                "role_id": None,  # Set this to your actual Discord role ID
                "perks": ["Placeholder perk A", "Placeholder perk B", "Placeholder perk C", "Placeholder perk D"]
            },
            "3": {
                "name": "TUI",
                "role_id": None,  # Set this to your actual Discord role ID
                "perks": ["Placeholder perk Alpha", "Placeholder perk Beta", "Placeholder perk Gamma", "Placeholder perk Delta", "Placeholder perk Epsilon"]
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

            # Apply perks immediately
            if tier == "1":
                users[uid]["max_pulls"] = 14  # +2 extra pulls
            elif tier == "2":
                users[uid]["max_pulls"] = 17  # +5 extra pulls
            elif tier == "3":
                users[uid]["max_pulls"] = 22  # +10 extra pulls

            save(USERS_FILE, users)

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

                # Reset max pulls to default
                users[uid]["max_pulls"] = 12

                save(USERS_FILE, users)

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
        """List all current patrons"""

        users = load(USERS_FILE)
        patrons = []

        for uid, user_data in users.items():
            if "patreon" in user_data:
                user = self.bot.get_user(int(uid))
                if user:
                    patrons.append({
                        "user": user,
                        "tier": user_data["patreon"]["tier"],
                        "name": user_data["patreon"]["name"]
                    })

        if not patrons:
            await ctx.send("📭 No current patrons found!")
            return

        embed = discord.Embed(
            title="👑 Current Patrons",
            description=f"Total patrons: {len(patrons)}",
            color=0xF1C40F
        )

        for patron in patrons:
            embed.add_field(
                name=f"{patron['user'].name} (Tier {patron['tier']})",
                value=f"**{patron['name']}** tier",
                inline=False
            )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Patreon(bot))
