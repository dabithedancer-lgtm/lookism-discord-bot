import discord
import time
import random
from discord.ext import commands
from discord.ui import View, Button
from utils.database import load, save
import config
import json

GANGS_FILE = "data/gangs.json"
USERS_FILE = "data/users.json"
WHITETIGER_FILE = "data/whitetiger.json"


class GangInviteView(View):
    def __init__(self, gang_cog, gid, gang, leader, member: discord.Member):
        super().__init__(timeout=120)
        self.gang_cog = gang_cog
        self.gid = gid
        self.gang = gang
        self.leader = leader
        self.member = member

        accept_button = Button(
            label="Accept", style=discord.ButtonStyle.success)
        deny_button = Button(label="Deny", style=discord.ButtonStyle.danger)

        async def accept_callback(interaction: discord.Interaction):
            if interaction.user.id != self.member.id:
                await interaction.response.send_message("❌ Only the invited user can respond to this invitation.", ephemeral=True)
                return

            gid, gang = self.gang_cog.get_gang(self.leader.id)
            if not gang or str(self.leader.id) != gang.get("leader") or gid != self.gid:
                for child in self.children:
                    child.disabled = True
                await interaction.response.edit_message(content="❌ This gang invitation is no longer valid.", view=self)
                return

            gang_type = gang.get("type", "gang")
            max_members = 10 if gang_type == "gang" else 50
            if len(gang.get("members", [])) >= max_members:
                for child in self.children:
                    child.disabled = True
                await interaction.response.edit_message(content=f"❌ This {gang_type} has reached its member cap.", view=self)
                return

            target_gid, target_gang = self.gang_cog.get_gang(self.member.id)
            if target_gang:
                for child in self.children:
                    child.disabled = True
                await interaction.response.edit_message(content=f"❌ {self.member.display_name} is already in **{target_gang.get('name', 'a gang')}**.", view=self)
                return

            gangs = load(GANGS_FILE)
            gang = gangs.get(self.gid, gang)
            if str(self.member.id) in gang.get("members", []):
                for child in self.children:
                    child.disabled = True
                await interaction.response.edit_message(content=f"ℹ️ {self.member.display_name} is already a member of **{gang.get('name', 'the gang')}**.", view=self)
                return

            gang.setdefault("members", []).append(str(self.member.id))
            gangs[self.gid] = gang
            save(GANGS_FILE, gangs)

            users = load(USERS_FILE)
            user_data = self.gang_cog.ensure_user(users, str(self.member.id))
            user_data["gang_name"] = gang.get("name")
            save(USERS_FILE, users)

            for child in self.children:
                child.disabled = True

            embed = discord.Embed(
                title="✅ Gang Join Approved",
                description=f"{self.member.mention} has joined **{gang.get('name', 'the gang')}**.",
                color=0x2ECC71,
            )
            await interaction.response.edit_message(content="", embed=embed, view=self)

        async def deny_callback(interaction: discord.Interaction):
            if interaction.user.id not in {self.member.id, self.leader.id}:
                await interaction.response.send_message("❌ Only the invited user or leader can deny this invitation.", ephemeral=True)
                return

            for child in self.children:
                child.disabled = True

            embed = discord.Embed(
                title="🚫 Gang Join Denied",
                description=f"Invitation for {self.member.mention} to join **{self.gang.get('name', 'the gang')}** was denied.",
                color=0xE74C3C,
            )
            await interaction.response.edit_message(content="", embed=embed, view=self)

        accept_button.callback = accept_callback
        deny_button.callback = deny_callback
        self.add_item(accept_button)
        self.add_item(deny_button)


class Gang(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_gang(self, uid):
        data = load(GANGS_FILE)
        for gid, g in data.items():
            if str(uid) in g['members']:
                return gid, g
        return None, None

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
                "gang_name": None
            }
        return users[uid]

    def load_white_tiger_agents(self):
        try:
            from utils.database import load as _load
            agents = _load(WHITETIGER_FILE)
            return agents or {}
        except Exception:
            return {}

    @commands.command(name="gang")
    async def gang(self, ctx, action: str = None, *, arg: str = ""):
        # Default: show your gang stats
        if action is None:
            gid, gang = self.get_gang(ctx.author.id)
            if not gang:
                embed = discord.Embed(
                    title="❌ Not in a Gang",
                    description="You're not in a gang! Create one with `ls gang create <name>`",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            gangs = load(GANGS_FILE)
            gang = gangs.get(gid, gang)
            gang.setdefault("exp", 0)

            members_count = len(gang.get("members", []))
            leader_mention = f"<@{gang['leader']}>"
            bank = gang.get("bank", 0)
            exp = int(gang.get("exp", 0))
            businesses_raw = gang.get("businesses", {})

            members_list = "\n".join([
                f"• <@{uid}>" + (" 👑" if uid == gang['leader'] else "")
                for uid in gang.get('members', [])
            ]) or "None"

            # Support both dict- and list-based businesses structures
            if isinstance(businesses_raw, dict):
                biz_iter = businesses_raw.values()
            elif isinstance(businesses_raw, list):
                biz_iter = businesses_raw
            else:
                biz_iter = []

            businesses_list = "\n".join([
                f"• {b.get('name', 'Unknown')} (💰 {b.get('income', 0):,}/day)"
                for b in biz_iter if isinstance(b, dict)
            ]) or "None"

            # XP bar (same rules as info): gang 50k / crew 150k EXP per level
            gang_type = gang.get("type", "gang")
            threshold = 50000 if gang_type == "gang" else 150000
            level = exp // threshold if threshold > 0 else 0
            progress = exp % threshold if threshold > 0 else 0
            ratio = progress / threshold if threshold > 0 else 0
            filled = int(ratio * 10)
            empty = 10 - filled
            bar = "█" * max(filled, 0) + "─" * max(empty, 0)
            xp_bar_text = (
                f"Lvl {level} {gang_type.title()}\n"
                f"[{bar}]\n"
                f"{progress:,}/{threshold:,} EXP"
            )

            embed = discord.Embed(
                title=f"👥 {gang['name']} — Gang Overview",
                description=(
                    "Welcome to your gang hub!\n\n"
                    "Use this to keep track of your crew's progress."
                ),
                color=0x3498DB
            )
            embed.set_author(name="Gang Stats",
                             icon_url=ctx.author.display_avatar.url)

            embed.add_field(name="👑 Leader", value=leader_mention, inline=True)
            embed.add_field(name="👥 Members",
                            value=f"`{members_count}`", inline=True)
            embed.add_field(
                name="💰 Bank", value=f"`{bank:,}` yen", inline=True)
            embed.add_field(name="⭐ Progress", value=xp_bar_text, inline=False)
            embed.add_field(name="🏢 Businesses",
                            value=businesses_list[:1024], inline=False)
            embed.add_field(name="📋 Members",
                            value=members_list[:1024], inline=False)

            embed.set_footer(
                text="Use `ls gang info` for a more detailed view, or `ls gang leave` to leave your gang.")
            return await ctx.send(embed=embed)

        if action == "create":
            if not arg:
                embed = discord.Embed(
                    title="❌ No Name Provided",
                    description="Usage: `ls gang create <name>`\n\nExample: `ls gang create Big Deal`",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            # Check if user is already in a gang
            gid, existing_gang = self.get_gang(ctx.author.id)
            if existing_gang:
                embed = discord.Embed(
                    title="❌ Already in a Gang",
                    description=f"You're already in **{existing_gang['name']}**!\n\nLeave your current gang first.",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            users = load(USERS_FILE)
            u = self.ensure_user(users, str(ctx.author.id))

            if u.get("yen", 0) < config.GANG_CREATE_COST:
                embed = discord.Embed(
                    title="❌ Insufficient Funds",
                    description=f"You need **{config.GANG_CREATE_COST:,}** yen to create a gang!\n\nCurrent balance: `{u.get('yen', 0):,}` yen",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            u["yen"] -= config.GANG_CREATE_COST
            save(USERS_FILE, users)

            gid = str(int(time.time()))
            new_gang = {
                "id": gid,
                "name": arg,
                "leader": str(ctx.author.id),
                "members": [str(ctx.author.id)],
                "bank": 0,
                "businesses": {},
                "raid_logs": [],
                "exp": 0,
                "level": 0,
                "type": "gang",
            }
            gangs = load(GANGS_FILE)
            gangs[gid] = new_gang
            save(GANGS_FILE, gangs)

            # Update user's gang name
            u["gang_name"] = arg
            save(USERS_FILE, users)

            embed = discord.Embed(
                title="✅ Gang Created!",
                description=f"**{arg}** has been created!",
                color=0x2ECC71
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            embed.add_field(name="👑 Leader",
                            value=f"<@{ctx.author.id}>", inline=True)
            embed.add_field(name="👥 Members", value="`1`", inline=True)
            embed.add_field(name="💰 Bank", value="`0` yen", inline=True)
            embed.set_footer(text="Use `ls gang add @user` to add members!")
            await ctx.send(embed=embed)

        elif action == "info":
            gid, gang = self.get_gang(ctx.author.id)
            if not gang:
                embed = discord.Embed(
                    title="❌ Not in a Gang",
                    description="You're not in a gang! Create one with `ls gang create <name>`",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            members_list = "\n".join(
                [f"• <@{uid}>" + (" 👑" if uid == gang['leader'] else "") for uid in gang['members']])

            businesses_raw = gang.get("businesses", {})
            if isinstance(businesses_raw, dict):
                biz_iter = businesses_raw.values()
            elif isinstance(businesses_raw, list):
                biz_iter = businesses_raw
            else:
                biz_iter = []

            businesses_list = "\n".join([
                f"• {b.get('name', 'Unknown')} (💰 {b.get('income', 0):,}/day)"
                for b in biz_iter if isinstance(b, dict)
            ]) or "None"

            # XP bar (same rules as overview):
            # gang: 50,000 EXP per level; crew: 150,000 EXP per level
            gang_type = gang.get("type", "gang")
            threshold = 50000 if gang_type == "gang" else 150000
            exp = int(gang.get("exp", 0))
            level = exp // threshold if threshold > 0 else 0
            progress = exp % threshold if threshold > 0 else 0
            ratio = progress / threshold if threshold > 0 else 0
            filled = int(ratio * 10)
            empty = 10 - filled
            bar = "█" * max(filled, 0) + "─" * max(empty, 0)
            # First line: level + type, second line: bar, third: numeric progress (e.g. 50/50000 EXP)
            xp_bar_text = (
                f"Lvl {level} {gang_type.title()}\n"
                f"[{bar}]\n"
                f"{progress:,}/{threshold:,} EXP"
            )

            embed = discord.Embed(
                title=f"👥 {gang['name']}",
                color=0x3498DB
            )
            embed.set_author(name="Gang Information",
                             icon_url=ctx.author.display_avatar.url)
            embed.add_field(name="👑 Leader",
                            value=f"<@{gang['leader']}>", inline=True)
            embed.add_field(name="👥 Members",
                            value=f"`{len(gang['members'])}`", inline=True)
            embed.add_field(
                name="💰 Bank", value=f"`{gang['bank']:,}` yen", inline=True)
            embed.add_field(name="⭐ Progress", value=xp_bar_text, inline=False)
            embed.add_field(name="📋 Members List",
                            value=members_list[:1024] or "None", inline=False)
            embed.add_field(name="🏢 Businesses",
                            value=businesses_list[:1024], inline=False)
            await ctx.send(embed=embed)

        elif action == "leave":
            gid, gang = self.get_gang(ctx.author.id)
            if not gang:
                embed = discord.Embed(
                    title="❌ Not in a Gang",
                    description="You're not in a gang!",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            if gang['leader'] == str(ctx.author.id):
                embed = discord.Embed(
                    title="❌ Leader Cannot Leave",
                    description="The leader cannot leave! Transfer leadership or disband the gang first.",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            gang['members'].remove(str(ctx.author.id))
            gangs = load(GANGS_FILE)
            gangs[gid] = gang
            save(GANGS_FILE, gangs)

            users = load(USERS_FILE)
            if str(ctx.author.id) in users:
                users[str(ctx.author.id)]["gang_name"] = None
            save(USERS_FILE, users)

            embed = discord.Embed(
                title="✅ Left Gang",
                description=f"You left **{gang['name']}**",
                color=0x2ECC71
            )
            await ctx.send(embed=embed)

        elif action in ["disband", "delete"]:
            # Leader-only: permanently dismantle the gang and clear members' gang_name
            gid, gang = self.get_gang(ctx.author.id)
            if not gang:
                embed = discord.Embed(
                    title="❌ Not in a Gang",
                    description="You're not in a gang!",
                    color=0xE74C3C,
                )
                return await ctx.send(embed=embed)

            if gang['leader'] != str(ctx.author.id):
                embed = discord.Embed(
                    title="❌ Leader Only",
                    description="Only the gang leader can dismantle the gang!",
                    color=0xE74C3C,
                )
                return await ctx.send(embed=embed)

            gangs = load(GANGS_FILE)
            users = load(USERS_FILE)

            # Clear gang_name for all members
            for member_id in gang.get("members", []):
                if str(member_id) in users:
                    users[str(member_id)]["gang_name"] = None

            # Remove gang from gangs.json
            if gid in gangs:
                del gangs[gid]

            save(GANGS_FILE, gangs)
            save(USERS_FILE, users)

            embed = discord.Embed(
                title="💥 Gang Dismantled",
                description=f"The gang **{gang['name']}** has been dismantled.",
                color=0xE74C3C,
            )
            embed.set_author(
                name=ctx.author.display_name,
                icon_url=ctx.author.display_avatar.url,
            )
            await ctx.send(embed=embed)

    @commands.command(name="gang_add", aliases=["gangadd"])
    async def gang_add(self, ctx, member: discord.Member = None):
        """Add a member to your gang. Usage: ls gang_add @user"""
        if not member:
            embed = discord.Embed(
                title="❌ No Member Specified",
                description="Usage: `ls gang_add @user`\n\nExample: `ls gang_add @user`",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if member.bot:
            embed = discord.Embed(
                title="❌ Cannot Add Bots",
                description="Bots cannot join gangs!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        gid, gang = self.get_gang(ctx.author.id)
        if not gang or gang['leader'] != str(ctx.author.id):
            embed = discord.Embed(
                title="❌ Leader Only",
                description="Only the gang leader can add members!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Enforce member caps based on type
        gang_type = gang.get("type", "gang")
        max_members = 10 if gang_type == "gang" else 50
        if len(gang.get("members", [])) >= max_members:
            embed = discord.Embed(
                title="❌ Member Limit Reached",
                description=f"This {gang_type} has reached its member cap (`{max_members}` members).",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Check if target is already in a gang
        target_gid, target_gang = self.get_gang(member.id)
        if target_gang:
            embed = discord.Embed(
                title="❌ Already in a Gang",
                description=f"{member.display_name} is already in **{target_gang['name']}**!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if str(member.id) in gang['members']:
            embed = discord.Embed(
                title="❌ Already a Member",
                description=f"{member.display_name} is already in your gang!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        view = GangInviteView(self, gid, gang, ctx.author, member)
        embed = discord.Embed(
            title="📨 Gang Invitation",
            description=f"{member.mention}, you have been invited to join **{gang['name']}** by {ctx.author.mention}.",
            color=0x3498DB,
        )
        embed.set_footer(
            text="Use the buttons below to accept or deny the invitation.")
        await ctx.send(content=member.mention, embed=embed, view=view)

    @commands.command(name="gang_remove", aliases=["gangremove", "gangkick"])
    async def gang_remove(self, ctx, member: discord.Member = None):
        """Remove a member from your gang. Usage: ls gang_remove @user"""
        if not member:
            embed = discord.Embed(
                title="❌ No Member Specified",
                description="Usage: `ls gang_remove @user`",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        gid, gang = self.get_gang(ctx.author.id)
        if not gang or gang['leader'] != str(ctx.author.id):
            embed = discord.Embed(
                title="❌ Leader Only",
                description="Only the gang leader can remove members!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if str(member.id) not in gang['members']:
            embed = discord.Embed(
                title="❌ Not a Member",
                description=f"{member.display_name} is not in your gang!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if gang['leader'] == str(member.id):
            embed = discord.Embed(
                title="❌ Cannot Remove Leader",
                description="You cannot remove yourself as leader!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        gang['members'].remove(str(member.id))
        gangs = load(GANGS_FILE)
        gangs[gid] = gang
        save(GANGS_FILE, gangs)

        users = load(USERS_FILE)
        if str(member.id) in users:
            users[str(member.id)]["gang_name"] = None
        save(USERS_FILE, users)

        embed = discord.Embed(
            title="✅ Member Removed",
            description=f"{member.mention} has been removed from **{gang['name']}**",
            color=0xE74C3C
        )
        await ctx.send(embed=embed)

    @commands.command(name="pay")
    async def pay(self, ctx, member: discord.Member = None, amount: int = None):
        if not member or not amount:
            embed = discord.Embed(
                title="❌ Missing Arguments",
                description="Usage: `ls pay @user <amount>`\n\nExample: `ls pay @user 5000`",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        gid, gang = self.get_gang(ctx.author.id)
        if not gang or gang['leader'] != str(ctx.author.id):
            embed = discord.Embed(
                title="❌ Leader Only",
                description="Only the gang leader can pay members!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be greater than 0!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        if gang['bank'] < amount:
            embed = discord.Embed(
                title="❌ Insufficient Gang Funds",
                description=f"Gang bank has `{gang['bank']:,}` yen, but you need `{amount:,}` yen!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        gang['bank'] -= amount
        users = load(USERS_FILE)
        user_data = self.ensure_user(users, str(member.id))
        user_data['yen'] = user_data.get('yen', 0) + amount
        save(USERS_FILE, users)

        gangs_data = load(GANGS_FILE)
        gangs_data[gid] = gang
        save(GANGS_FILE, gangs_data)

        embed = discord.Embed(
            title="💸 Payment Sent",
            description=f"Paid **{amount:,}** yen to {member.mention}!",
            color=0x2ECC71
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="💰 Remaining Bank",
                        value=f"`{gang['bank']:,}` yen", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="addgangfunds", aliases=["add_gangfunds", "addfunds", "gangfunds"])
    async def add_gang_funds(self, ctx, amount: int = None):
        if amount is None or amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Usage: `ls addgangfunds <amount>`\n\nExample: `ls addgangfunds 50000`",
                color=0xE74C3C,
            )
            return await ctx.send(embed=embed)

        gid, gang = self.get_gang(ctx.author.id)
        if not gang:
            embed = discord.Embed(
                title="❌ Not in a Gang",
                description="You must be in a gang to add funds to its bank.",
                color=0xE74C3C,
            )
            return await ctx.send(embed=embed)

        users = load(USERS_FILE)
        user = self.ensure_user(users, str(ctx.author.id))
        if user.get("yen", 0) < amount:
            embed = discord.Embed(
                title="❌ Not Enough Yen",
                description=f"You don't have enough yen to deposit that amount. Current balance: `{user.get('yen', 0):,}` yen.",
                color=0xE74C3C,
            )
            return await ctx.send(embed=embed)

        user["yen"] = user.get("yen", 0) - amount
        users[str(ctx.author.id)] = user
        save(USERS_FILE, users)

        gang["bank"] = gang.get("bank", 0) + amount
        gangs = load(GANGS_FILE)
        gangs[gid] = gang
        save(GANGS_FILE, gangs)

        embed = discord.Embed(
            title="🏦 Funds Added to Gang Bank",
            description=f"You deposited **{amount:,}** yen into **{gang.get('name', 'your gang')}**'s bank.",
            color=0x2ECC71,
        )
        embed.add_field(name="💰 Your New Balance",
                        value=f"`{user.get('yen', 0):,}` yen", inline=True)
        embed.add_field(name="🏦 Gang Bank Balance",
                        value=f"`{gang.get('bank', 0):,}` yen", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="business_create", aliases=["biz"])
    async def bus_create(self, ctx, *, name: str = None):
        if not name:
            embed = discord.Embed(
                title="❌ No Name Provided",
                description="Usage: `ls business_create <name>`\n\nExample: `ls business_create Restaurant`",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        gid, gang = self.get_gang(ctx.author.id)
        if not gang or gang['leader'] != str(ctx.author.id):
            embed = discord.Embed(
                title="❌ Leader Only",
                description="Only the gang leader can create businesses!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Ensure businesses is a dict (migrate from old list format if needed)
        if isinstance(gang.get('businesses', {}), list):
            migrated = {}
            for old in gang['businesses']:
                if isinstance(old, dict):
                    bid_old = old.get('id') or f"b_{int(time.time())}"
                    migrated[bid_old] = {
                        "name": old.get("name", "Unknown"),
                        "income": old.get("income", 0),
                        "is_stolen": old.get("is_stolen", False),
                    }
            gang['businesses'] = migrated

        if len(gang['businesses']) >= 2:
            embed = discord.Embed(
                title="❌ Business Limit Reached",
                description="Maximum 2 businesses per gang!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        cost = 100_000
        if gang.get("bank", 0) < cost:
            embed = discord.Embed(
                title="❌ Insufficient Gang Funds",
                description=f"Your gang bank needs **{cost:,}** yen to buy a new business. Current bank: `{gang.get('bank', 0):,}` yen.",
                color=0xE74C3C,
            )
            return await ctx.send(embed=embed)

        gang["bank"] = gang.get("bank", 0) - cost

        income = random.choice([25000, 40000, 50000, 60000])
        bid = f"b_{int(time.time())}"
        gang.setdefault('businesses', {})[bid] = {
            "name": name,
            "income": income,
            "is_stolen": False,
        }

        gangs_data = load(GANGS_FILE)
        gangs_data[gid] = gang
        save(GANGS_FILE, gangs_data)

        embed = discord.Embed(
            title="🏢 Business Created!",
            description=f"**{name}** is now operational!",
            color=0x2ECC71
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="💰 Daily Income",
                        value=f"`{income:,}` yen/day", inline=True)
        embed.add_field(name="📊 Total Businesses",
                        value=f"`{len(gang['businesses'])}/2`", inline=True)
        embed.set_footer(text="Businesses generate income daily!")
        await ctx.send(embed=embed)

    @commands.command(name="businessrework", aliases=["bre"])
    async def business_rework(self, ctx, *, name: str = None):
        """Rework one of your gang businesses to reroll its income. Usage: ls businessrework [business name]"""
        gid, gang = self.get_gang(ctx.author.id)
        if not gang or gang['leader'] != str(ctx.author.id):
            embed = discord.Embed(
                title="❌ Leader Only",
                description="Only the gang leader can rework businesses!",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Cost: 100,000 yen from leader's personal balance
        users = load(USERS_FILE)
        leader = self.ensure_user(users, str(ctx.author.id))
        cost = 100_000
        if leader.get("yen", 0) < cost:
            embed = discord.Embed(
                title="❌ Not Enough Yen",
                description=f"You need **{cost:,}** yen to rework a business!\n\nCurrent balance: `{leader.get('yen', 0):,}` yen",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        leader["yen"] = leader.get("yen", 0) - cost
        users[str(ctx.author.id)] = leader
        save(USERS_FILE, users)

        # Ensure businesses is a dict (migrate from old list format if needed)
        if isinstance(gang.get('businesses', {}), list):
            migrated = {}
            for old in gang['businesses']:
                if isinstance(old, dict):
                    bid_old = old.get('id') or f"b_{int(time.time())}"
                    migrated[bid_old] = {
                        "name": old.get("name", "Unknown"),
                        "income": old.get("income", 0),
                        "is_stolen": old.get("is_stolen", False),
                    }
            gang['businesses'] = migrated

        businesses = gang.get('businesses', {})
        if not businesses:
            embed = discord.Embed(
                title="❌ No Businesses",
                description="Your gang has no businesses to rework. Create one first with `ls business_create <name>`.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Select target business
        target_id = None
        target_biz = None

        # If only one business and no name provided, use it
        if len(businesses) == 1 and not name:
            target_id, target_biz = next(iter(businesses.items()))
        else:
            if not name:
                # Ask user to specify which business
                biz_names = ", ".join(
                    f"**{b['name']}**" for b in businesses.values())
                embed = discord.Embed(
                    title="❌ Specify Business",
                    description=f"You have multiple businesses. Please specify which one to rework.\n\nAvailable: {biz_names}",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

            # Case-insensitive match on business name
            name_lower = name.lower()
            for bid, b in businesses.items():
                if str(b.get('name', '')).lower() == name_lower:
                    target_id, target_biz = bid, b
                    break

            if target_biz is None:
                embed = discord.Embed(
                    title="❌ Business Not Found",
                    description=f"No business named **{name}** was found in your gang.",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

        old_income = int(target_biz.get('income', 0))

        # Reroll income: values between 25k and 60k (using existing high tiers)
        possible_incomes = [25000, 40000, 50000, 60000]
        new_income = random.choice(possible_incomes)
        # Try to avoid rolling the exact same income if possible
        if len(possible_incomes) > 1:
            attempts = 0
            while new_income == old_income and attempts < 5:
                new_income = random.choice(possible_incomes)
                attempts += 1

        target_biz['income'] = new_income
        businesses[target_id] = target_biz
        gang['businesses'] = businesses

        gangs_data = load(GANGS_FILE)
        gangs_data[gid] = gang
        save(GANGS_FILE, gangs_data)

        embed = discord.Embed(
            title="🔁 Business Reworked",
            description=f"**{target_biz.get('name', 'Unknown')}** has been reworked!",
            color=0xF1C40F
        )
        embed.add_field(name="Old Income",
                        value=f"`{old_income:,}` yen/day", inline=True)
        embed.add_field(name="New Income",
                        value=f"`{new_income:,}` yen/day", inline=True)
        embed.set_footer(
            text="Reworking changes only the income range (25k–60k).")
        await ctx.send(embed=embed)

    @commands.command(name="raid_log", aliases=["logs"])
    async def raid_log(self, ctx):
        _, gang = self.get_gang(ctx.author.id)
        if not gang:
            embed = discord.Embed(
                title="❌ Not in a Gang",
                description="You're not in a gang! Join or create one first.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        logs = gang.get("raid_logs", [])
        if not logs:
            embed = discord.Embed(
                title="📋 Raid Logs",
                description="No raid logs yet!",
                color=0x95A5A6
            )
            embed.set_author(name=gang['name'],
                             icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        desc = "\n".join(
            [f"• **{l.get('attacker', 'Unknown')}** - {l.get('outcome', 'Unknown')}" for l in logs[-10:]])

        embed = discord.Embed(
            title="📋 Raid Logs",
            description=desc,
            color=0x3498DB
        )
        embed.set_author(name=gang['name'],
                         icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Showing last {min(10, len(logs))} entries")
        await ctx.send(embed=embed)

    @commands.command(name="cs", aliases=["counter"])
    async def cs(self, ctx, target: str = None):
        if not target:
            embed = discord.Embed(
                title="❌ No Target",
                description="Usage: `ls cs <target>`\n\nSearch for a target in raid logs.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title="⚔️ Counter Strike",
            description=f"Searching for **{target}** in raid logs...",
            color=0xF1C40F
        )
        embed.set_footer(text="Feature coming soon!")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Gang(bot))
