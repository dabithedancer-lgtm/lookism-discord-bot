import discord
import random
import asyncio
import time
import config
from discord.ext import commands
from discord.ui import View, Button, button
from utils.database import load, save
from utils.game_math import regenerate_pulls

USERS_FILE = "data/users.json"
CARDS_FILE = "data/cards.json"
RARITIES_FILE = "data/rarities.json"
BOSSES_FILE = "data/bosses.json"
EMOJI_FILE = "data/emoji.json"


def has_patreon_role(member):
    """Check if member has any patreon role or is marked as a patron in the database"""
    if not member:
        return False

    try:
        # First check database
        users = load(USERS_FILE)
        uid = str(member.id)
        if uid in users and "patreon" in users[uid]:
            # Check if the subscription is still valid
            if users[uid]["patreon"].get("expires_at", 0) > time.time():
                return True

        # Then check roles
        if hasattr(member, 'roles'):
            member_role_ids = [role.id for role in member.roles]
            return any(role_id in config.PATREON_ROLES for role_id in member_role_ids)

        return False
    except Exception as e:
        print(f"Error checking patreon status for {member}: {e}")
        return False


class PullAgainView(View):
    """(Deprecated) Previously used for a 'Pull Again' button. Kept for compatibility but no longer used."""

    def __init__(self, ctx):
        super().__init__(timeout=120)
        self.ctx = ctx


class Gacha(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def ensure_user(self, users, uid):
        """Ensure user exists in database"""
        if uid not in users:
            users[uid] = {
                "pulls": config.MAX_PULLS,
                "max_pulls": config.MAX_PULLS,
                "yen": 0,
                "cards": [],
                "fragments": {},
                "unlocked": [],
                "chests": {},
                "tickets": {},
                "equipment": {},
                "wins": 0,
                "streak": 0,
                "last_pull_regen_ts": int(time.time())
            }
        else:
            users[uid]["max_pulls"] = max(users[uid].get(
                "max_pulls", config.MAX_PULLS), config.MAX_PULLS)
            users[uid]["pulls"] = min(users[uid].get(
                "pulls", config.MAX_PULLS), users[uid]["max_pulls"])
            if "last_pull_regen_ts" not in users[uid]:
                users[uid]["last_pull_regen_ts"] = int(time.time())
        return users[uid]

    def get_card_type(self, stats):
        """Determine card type based on stats"""
        attack = stats.get('attack', 0)
        health = stats.get('health', 0)
        speed = stats.get('speed', 0)

        if health == 0:
            return "Unknown"

        if health >= (speed + (attack * 0.7)):
            return "Tank"
        elif health >= (speed + attack) * 0.5:
            return "Balanced"
        else:
            if speed >= (health * 0.65):
                return "Speedster"
            elif attack >= (health * 0.5):
                return "Striker"
            elif abs(speed - attack) <= (max(speed, attack) * 0.1):
                return "Prodigy"
            else:
                return "Balanced"

    @commands.command(name="pull")
    async def pull(self, ctx):
        """Summon a character! Usage: ls pull"""
        users = load(USERS_FILE)
        uid = str(ctx.author.id)
        user = self.ensure_user(users, uid)

        if "max_pulls" not in user:
            user["max_pulls"] = config.MAX_PULLS

        user = regenerate_pulls(user)

        max_pulls = user["max_pulls"]
        if user.get("pulls", 0) > max_pulls:
            user["pulls"] = max_pulls
            user["last_pull_regen_ts"] = int(time.time())

        users[uid] = user
        save(USERS_FILE, users)

        current_pulls = user.get("pulls", 0)
        if current_pulls <= 0:
            embed = discord.Embed(
                title="❌ Out of Pulls!",
                description=f"You have `0/{max_pulls}` pulls left.\n\nUse `ls cd` to check cooldowns.",
                color=0xE74C3C
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        # Animation
        embed = discord.Embed(
            title="✨ Summoning Character...",
            description="The summoning orb is glowing...",
            color=0x5865F2
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        print(f"Using GIF URL: {config.IMG_SUMMON_ORB}")
        embed.set_image(url=config.IMG_SUMMON_ORB)
        embed.set_footer(text="Summoning in progress...")
        try:
            msg = await ctx.send(embed=embed)
        except Exception as e:
            print(f"Error sending embed with GIF: {e}")
            # Fallback without GIF
            embed.remove_image()
            msg = await ctx.send(embed=embed)

        await asyncio.sleep(random.uniform(1.0, 2.0))

        # Logic
        user["pulls"] -= 1

        # 1. Ticket Logic (2.5% Chance)
        ticket_drop = None
        try:
            bosses = load(BOSSES_FILE)
            if bosses and random.random() * 100 <= 2.5:
                # Weighted choice
                total = sum(b.get('ticket_drop_rate', 0)
                            for b in bosses.values())
                if total > 0:
                    r = random.uniform(0, total)
                    curr = 0
                    for b in bosses.values():
                        curr += b.get('ticket_drop_rate', 0)
                        if r <= curr:
                            ticket_drop = b
                            break

            if ticket_drop:
                user.setdefault("tickets", {})
                tid = f"{ticket_drop.get('name', '').lower().replace(' ', '_')}_ticket"
                user["tickets"][tid] = user["tickets"].get(tid, 0) + 1
        except Exception as e:
            print(f"Error loading bosses: {e}")

        # 2. Card Logic
        cards_dict = load(CARDS_FILE)
        rarities = load(RARITIES_FILE)

        if not cards_dict:
            embed = discord.Embed(
                title="❌ No Cards Available",
                description="Card database is empty! Please add cards first.",
                color=0xE74C3C
            )
            await msg.edit(embed=embed)
            return

        cards_list = list(cards_dict.values())
        weights = []
        for card in cards_list:
            rarity_key = card.get('rarity', 'C')
            rarity_info = rarities.get(rarity_key, {})
            weight = rarity_info.get('weight_multiplier', 5)
            weights.append(weight)

        chosen = random.choices(cards_list, weights=weights, k=1)[0]
        chosen_rarity = chosen.get('rarity', 'C')
        rarity_info = rarities.get(chosen_rarity, {})

        user.setdefault("cards", [])
        user.setdefault("unlocked", [])
        is_new = False
        card_name = chosen.get('name', 'Unknown')

        if card_name not in user.get("unlocked", []):
            is_new = True
            user.setdefault("unlocked", []).append(card_name)
            user["cards"].append({
                "name": card_name,
                "rarity": chosen_rarity,
                "level": 1,
                "exp": 0,
                "evo": 0,
                "aura": 0
            })
        else:
            user.setdefault("fragments", {})
            user["fragments"][card_name] = user["fragments"].get(
                card_name, 0) + 1

        users[uid] = user
        save(USERS_FILE, users)

        # Result Embed
        try:
            rarity_color = rarity_info.get("color", "#5865F2")
            col = int(rarity_color.replace("#", ""), 16)
        except:
            col = 0x5865F2

        rarity_display = rarity_info.get("display_name", chosen_rarity)
        rarity_emoji = rarity_info.get("emoji", "⭐")

        title = card_name
        description = f"**{rarity_display}** ({chosen_rarity})"

        final_embed = discord.Embed(
            title=title,
            description=description,
            color=col
        )
        final_embed.set_author(name=ctx.author.display_name,
                               icon_url=ctx.author.display_avatar.url)

        if rarity_info.get("icon"):
            final_embed.set_thumbnail(url=rarity_info["icon"])

        card_images = chosen.get("images", {})
        if card_images.get("evo_1"):
            final_embed.set_image(url=card_images["evo_1"])

        card_stats = chosen.get("stats", {})
        if card_stats.get("evo_1"):
            stats = card_stats["evo_1"]
            attack = stats.get('attack', 'N/A')
            health = stats.get('health', 'N/A')
            speed = stats.get('speed', 'N/A')

            card_type = self.get_card_type(stats)
            stats_text = f"**Strength:** `{attack}`\n**Health:** `{health}`\n**Speed:** `{speed}`"
            final_embed.add_field(
                name="📊 Base Stats (Evo 1)", value=stats_text, inline=False)
            final_embed.add_field(
                name="🎯 Type", value=f"**{card_type}**", inline=True)

        if chosen.get("ability") and chosen.get("ability") != "None":
            final_embed.add_field(
                name="✨ Ability", value=chosen.get("ability"), inline=False)

        max_pulls = user.get("max_pulls", config.MAX_PULLS)
        footer_parts = [f"Pulls: {user['pulls']}/{max_pulls}"]

        if not is_new:
            frag_count = user["fragments"].get(card_name, 0)
            footer_parts.append(f"Shards: {frag_count}")

        final_embed.set_footer(text=" • ".join(footer_parts))
        await msg.edit(embed=final_embed, view=None)


async def setup(bot):
    await bot.add_cog(Gacha(bot))
