import discord
from discord.ext import commands
from discord.ui import View, Select, Button
from utils.database import load, save
from utils.game_math import compute_stats

USERS_FILE = "data/users.json"
WEAPONS_FILE = "data/weapons.json"
CARDS_FILE = "data/cards.json"
RARITIES_FILE = "data/rarities.json"
EMOJI_FILE = "data/emoji.json"


class CardNavigationView(View):
    """View for navigating through cards one by one"""

    def __init__(self, ctx, cards, cards_db, rarities, info_type, start_index=0, show_evo_buttons=False):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.cards = cards
        self.cards_db = cards_db
        self.rarities = rarities
        self.info_type = info_type  # "database" or "owned"
        self.current_index = start_index
        self.current_evo = 1
        self.show_evo_buttons = show_evo_buttons
        self.message = None

        # Add navigation buttons only if there are multiple cards
        if len(cards) > 1:
            self.add_item(CardNavigationButton("previous", "⬅️ Previous", 0))
            self.add_item(CardNavigationButton("next", "➡️ Next", 0))

        # Add evolution buttons only for specific card lookups
        if show_evo_buttons:
            self.add_item(CardEvoButton("evo_1", "Evo 1", 1))
            self.add_item(CardEvoButton("evo_2", "Evo 2", 1))
            self.add_item(CardEvoButton("evo_3", "Evo 3", 1))
            self.add_item(CardEvoButton("evo_4", "Evo 4", 1))

        # Disable buttons if at start/end
        self.update_buttons()

    def update_buttons(self):
        """Enable/disable buttons based on current position"""
        button_index = 0

        # Update navigation buttons if they exist
        if len(self.cards) > 1:
            prev_button = self.children[0]
            next_button = self.children[1]

            prev_button.disabled = self.current_index <= 0
            next_button.disabled = self.current_index >= len(self.cards) - 1
            button_index = 2  # Evo buttons start after nav buttons

        # Update evolution button states
        if self.show_evo_buttons and len(self.cards) == 1:
            for i in range(button_index, len(self.children)):
                if isinstance(self.children[i], CardEvoButton):
                    evo_num = int(self.children[i].evo_level.split('_')[1])
                    self.children[i].disabled = (evo_num == self.current_evo)
                    # Change style for active button
                    if evo_num == self.current_evo:
                        self.children[i].style = discord.ButtonStyle.success
                    else:
                        self.children[i].style = discord.ButtonStyle.secondary

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ This isn't your navigation menu!", ephemeral=True)
            return False
        return True

    def create_card_embed(self, card_index):
        """Create embed for a specific card"""
        if self.info_type == "database":
            card = self.cards[card_index]
        else:  # owned
            owned_card = self.cards[card_index]
            card = next((c for c in self.cards_db.values() if c.get(
                'name') == owned_card.get('name')), None)
            if not card:
                return None

        if not card:
            return None

        # Get rarity info
        rarity_key = card.get('rarity', 'C')
        rarity_info = self.rarities.get(rarity_key, {})
        rarity_display = rarity_info.get("display_name", rarity_key)
        rarity_emoji = rarity_info.get("emoji", "⭐")

        # Get rarity color
        rarity_color = rarity_info.get("color", "#5865F2")
        try:
            col = int(rarity_color.replace("#", ""), 16)
        except:
            col = 0x5865F2

        # Create embed
        if self.info_type == "database":
            embed = discord.Embed(
                title=f"{rarity_emoji} {card.get('name', 'Unknown')}",
                description=f"**{rarity_display}** ({rarity_key}) - Card {card_index + 1}/{len(self.cards)}",
                color=col
            )
            embed.set_author(name="Card Information",
                             icon_url=self.ctx.author.display_avatar.url)

            # Set card image based on current evolution (if evo buttons are shown)
            card_images = card.get("images", {})
            if self.show_evo_buttons:
                evo_key = f"evo_{self.current_evo}"
                if card_images.get(evo_key):
                    embed.set_image(url=card_images[evo_key])
                elif card_images.get("evo_1"):
                    embed.set_image(url=card_images["evo_1"])
            else:
                if card_images.get("evo_1"):
                    embed.set_image(url=card_images["evo_1"])

            # Add stats for current evolution
            card_stats = card.get("stats", {})
            if self.show_evo_buttons:
                evo_key = f"evo_{self.current_evo}"
                if card_stats.get(evo_key):
                    stats = card_stats[evo_key]
                    embed.add_field(
                        name=f"📊 Stats (Evo {self.current_evo})",
                        value=f"**Strength:** `{stats.get('attack', 'N/A')}`\n**Health:** `{stats.get('health', 'N/A')}`\n**Speed:** `{stats.get('speed', 'N/A')}`",
                        inline=False
                    )
            else:
                # Only show base stats for list browsing
                if card_stats.get("evo_1"):
                    stats = card_stats["evo_1"]
                    embed.add_field(
                        name="📊 Base Stats (Evo 1)",
                        value=f"**Strength:** `{stats.get('attack', 'N/A')}`\n**Health:** `{stats.get('health', 'N/A')}`\n**Speed:** `{stats.get('speed', 'N/A')}`",
                        inline=False
                    )

        else:  # owned card
            embed = discord.Embed(
                title=f"{rarity_emoji} {owned_card.get('name', 'Unknown')}",
                description=f"**{rarity_display}** ({rarity_key}) - **Your Card** - Card {card_index + 1}/{len(self.cards)}",
                color=col
            )
            embed.set_author(name=f"{self.ctx.author.display_name}'s Card Info",
                             icon_url=self.ctx.author.display_avatar.url)

            # Set card image based on evolution
            card_images = card.get("images", {})
            evo_level = owned_card.get('evo', 0)

            if self.show_evo_buttons:
                evo_key = f"evo_{self.current_evo}"
                if card_images.get(evo_key):
                    embed.set_image(url=card_images[evo_key])
                elif card_images.get("evo_1"):
                    embed.set_image(url=card_images["evo_1"])
            else:
                # Show current evolution image
                if evo_level >= 3 and card_images.get("evo_4"):
                    embed.set_image(url=card_images["evo_4"])
                elif evo_level >= 2 and card_images.get("evo_3"):
                    embed.set_image(url=card_images["evo_3"])
                elif evo_level >= 1 and card_images.get("evo_2"):
                    embed.set_image(url=card_images["evo_2"])
                elif card_images.get("evo_1"):
                    embed.set_image(url=card_images["evo_1"])

            # Current stats with computed values
            current_stats = compute_stats(card, owned_card.get(
                'level', 1), owned_card.get('aura', 0), owned_card.get('equipped_item_id'))
            embed.add_field(
                name="📊 Current Stats",
                value=f"**Strength:** `{current_stats['attack']}`\n**Health:** `{current_stats['health']}`\n**Speed:** `{current_stats['speed']}`",
                inline=False
            )

            # Card progression info
            embed.add_field(
                name="📈 Card Progress",
                value=f"**Level:** `{owned_card.get('level', 1)}`\n**Evolution:** `{owned_card.get('evo', 0)}/3`\n**Aura Points:** `{owned_card.get('aura', 0)}`\n**Experience:** `{owned_card.get('exp', 0)}`",
                inline=True
            )

            # Equipment info
            if owned_card.get('equipped_item_id'):
                weapons = load(WEAPONS_FILE)
                weapon = weapons.get(owned_card['equipped_item_id'])
                if weapon:
                    embed.add_field(
                        name="⚔️ Equipped Weapon",
                        value=f"**{weapon['name']}**\n{weapon.get('description', 'No description')}",
                        inline=True
                    )

            # Base stats comparison (only if not showing evo buttons)
            if not self.show_evo_buttons:
                base_stats = card.get("stats", {}).get("evo_1", {})
                if base_stats:
                    embed.add_field(
                        name="📋 Base Stats (Evo 1)",
                        value=f"**Strength:** `{base_stats.get('attack', 'N/A')}`\n**Health:** `{base_stats.get('health', 'N/A')}`\n**Speed:** `{base_stats.get('speed', 'N/A')}`",
                        inline=False
                    )

        # Add ability if available
        if card.get("ability") and card.get("ability") != "None":
            embed.add_field(name="✨ Ability", value=card.get(
                "ability"), inline=False)

        return embed

    async def update_display(self, interaction):
        """Update the displayed card"""
        self.update_buttons()
        embed = self.create_card_embed(self.current_index)
        if embed:
            await interaction.response.edit_message(embed=embed, view=self)


class CardNavigationButton(Button):
    """Button for navigating between cards"""

    def __init__(self, direction, label, row):
        super().__init__(style=discord.ButtonStyle.primary, label=label, row=row)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, CardNavigationView):
            if self.direction == "previous":
                view.current_index = max(0, view.current_index - 1)
            elif self.direction == "next":
                view.current_index = min(
                    len(view.cards) - 1, view.current_index + 1)

            # Reset evolution when changing cards
            view.current_evo = 1
            await view.update_display(interaction)


class CardEvoButton(Button):
    """Button for switching between evolution stages"""

    def __init__(self, evo_level, label, row):
        super().__init__(style=discord.ButtonStyle.secondary, label=label, row=row)
        self.evo_level = evo_level

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, CardNavigationView):
            view.current_evo = int(self.evo_level.split('_')[1])
            await view.update_display(interaction)


def ensure_user(users, uid):
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


def load_emojis():
    """Load emoji mappings for cards and ensure all card names exist as keys.

    Structure in emoji.json:
    {
        "Card Name": "",
        ...
    }
    You can later fill in actual emoji IDs or codes.
    """
    emojis = load(EMOJI_FILE, default={}) or {}
    cards_db = load(CARDS_FILE)

    updated = False
    for card in cards_db.values():
        name = card.get("name")
        if name and name not in emojis:
            emojis[name] = ""
            updated = True

    if updated:
        save(EMOJI_FILE, emojis)

    return emojis


class InventorySelect(Select):
    def __init__(self, user_cards):
        options = []
        # Limit to 25 for discord select menu
        for i, c in enumerate(user_cards[:25]):
            item_status = " ⚔️" if c.get('equipped_item_id') else ""
            options.append(discord.SelectOption(
                label=c['name'][:100],
                description=f"Lv.{c['level']} {c.get('rarity', 'Common')}{item_status}",
                value=str(i)
            ))

        super().__init__(placeholder="🔍 Select a card to view details...",
                         min_values=1, max_values=1, options=options)
        self.user_cards = user_cards

    async def callback(self, interaction):
        idx = int(self.values[0])
        card = self.user_cards[idx]

        # Get base card data for stats
        cards_db = load(CARDS_FILE)
        base_card = next((v for v in cards_db.values()
                         if v['name'] == card['name']), None)

        embed = discord.Embed(
            title=f"🎴 {card['name']}",
            color=0x5865F2
        )
        embed.set_author(name="Card Details",
                         icon_url=interaction.user.display_avatar.url)

        embed.add_field(
            name="📊 Level", value=f"`{card['level']}`", inline=True)
        embed.add_field(name="⭐ Rarity", value=card.get(
            'rarity', 'Common'), inline=True)
        embed.add_field(name="💎 Evolution",
                        value=f"`{card.get('evo', 0)}`", inline=True)

        if base_card:
            stats = compute_stats(base_card, card['level'], card.get(
                'aura', 0), card.get('equipped_item_id'))
            embed.add_field(
                name="⚔️ Stats",
                value=f"**ATK:** `{stats['attack']}`\n**HP:** `{stats['health']}`\n**SPD:** `{stats['speed']}`",
                inline=False
            )

        if card.get('equipped_item_id'):
            weapons = load(WEAPONS_FILE)
            weapon = weapons.get(card['equipped_item_id'])
            if weapon:
                embed.add_field(name="⚔️ Equipment",
                                value=weapon['name'], inline=True)

        if base_card and base_card.get("images", {}).get("evo_1"):
            embed.set_image(url=base_card["images"]["evo_1"])

        await interaction.response.send_message(embed=embed, ephemeral=True)


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ci", aliases=["cardinfo"])
    async def card_info(self, ctx, *, card_name: str = None):
        """Show information about a specific card. Usage: ls ci <card_name> or ls ci all or ls ci <rarity>"""
        cards_db = load(CARDS_FILE)
        rarities = load(RARITIES_FILE)

        # Handle "all" case
        if card_name and card_name.lower() == "all":
            return await self._show_all_cards(ctx, cards_db, rarities, "database")

        # Handle rarity case
        if card_name and card_name.upper() in rarities:
            return await self._show_rarity_cards(ctx, cards_db, rarities, card_name.upper(), "database")

        if not card_name:
            embed = discord.Embed(
                title="❌ Missing Card Name",
                description="Usage: `ls ci <card_name>`\n\nExamples:\n• `ls ci Gun Park`\n• `ls ci all` (show all cards)\n• `ls ci SR` (show Super Rare cards)\n• `ls ci UR` (show Ultra Rare cards)",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Search for card (case-insensitive, partial match)
        card = None
        search_lower = card_name.lower()

        # Exact match first (filter out tickets)
        for c in cards_db.values():
            if c.get('name', '').lower() == search_lower and not c.get('id', '').endswith('_ticket'):
                card = c
                break

        # Partial match if no exact match (filter out tickets)
        if not card:
            matches = [c for c in cards_db.values() if search_lower in c.get(
                'name', '').lower() and not c.get('id', '').endswith('_ticket')]
            if len(matches) >= 1:
                # Show all matching cards one by one with navigation
                view = CardNavigationView(
                    ctx, matches, cards_db, rarities, "database", show_evo_buttons=True)
                embed = view.create_card_embed(0)

                if embed:
                    message = await ctx.send(embed=embed, view=view)
                    view.message = message
                return
            else:
                embed = discord.Embed(
                    title="❌ Card Not Found",
                    description=f"Could not find any card matching: **{card_name}**\n\nTry `ls ci all` to see all cards or `ls ci <rarity>` for rarity-specific cards.",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

        if not card:
            embed = discord.Embed(
                title="❌ Card Not Found",
                description=f"Could not find any card matching: **{card_name}**\n\nTry `ls ci all` to see all cards or `ls ci <rarity>` for rarity-specific cards.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Create navigation view with evolution buttons for specific card lookup
        view = CardNavigationView(
            ctx, [card], cards_db, rarities, "database", show_evo_buttons=True)
        embed = view.create_card_embed(0)

        if embed:
            message = await ctx.send(embed=embed, view=view)
            view.message = message

    async def _show_all_cards(self, ctx, cards_db, rarities, info_type):
        """Show all cards in the database or owned cards with navigation"""
        if info_type == "database":
            # Filter out tickets from database cards
            cards = [c for c in cards_db.values() if not c.get(
                'id', '').endswith('_ticket')]
            if not cards:
                embed = discord.Embed(
                    title="📚 No Cards Found",
                    description="No cards found in the database!",
                    color=0x95A5A6
                )
                return await ctx.send(embed=embed)
        else:  # owned
            users = load(USERS_FILE)
            user = ensure_user(users, str(ctx.author.id))
            cards = user.get("cards", [])
            if not cards:
                embed = discord.Embed(
                    title="📚 No Cards Found",
                    description="You don't own any cards yet!\n\nUse `ls pull` to get characters.",
                    color=0x95A5A6
                )
                embed.set_author(name=ctx.author.display_name,
                                 icon_url=ctx.author.display_avatar.url)
                return await ctx.send(embed=embed)

        # Create navigation view
        view = CardNavigationView(ctx, cards, cards_db, rarities, info_type)
        embed = view.create_card_embed(0)

        if embed:
            message = await ctx.send(embed=embed, view=view)
            view.message = message

    async def _show_rarity_cards(self, ctx, cards_db, rarities, rarity_key, info_type):
        """Show cards of a specific rarity with navigation"""
        rarity_info = rarities.get(rarity_key, {})
        rarity_display = rarity_info.get("display_name", rarity_key)
        rarity_emoji = rarity_info.get("emoji", "⭐")

        if info_type == "database":
            # Filter out tickets from database cards by rarity
            cards = [c for c in cards_db.values() if c.get(
                'rarity') == rarity_key and not c.get('id', '').endswith('_ticket')]
            if not cards:
                embed = discord.Embed(
                    title=f"{rarity_emoji} No {rarity_display} Cards",
                    description=f"No {rarity_display} cards found in the database!",
                    color=0x95A5A6
                )
                return await ctx.send(embed=embed)
        else:  # owned
            users = load(USERS_FILE)
            user = ensure_user(users, str(ctx.author.id))
            owned_cards = user.get("cards", [])
            cards = []
            for owned_card in owned_cards:
                base_card = next((b for b in cards_db.values() if b.get(
                    'name') == owned_card.get('name')), None)
                if base_card and base_card.get('rarity') == rarity_key:
                    cards.append(owned_card)

            if not cards:
                embed = discord.Embed(
                    title=f"{rarity_emoji} No {rarity_display} Cards",
                    description=f"You don't own any {rarity_display} cards!",
                    color=0x95A5A6
                )
                embed.set_author(name=ctx.author.display_name,
                                 icon_url=ctx.author.display_avatar.url)
                return await ctx.send(embed=embed)

        # Create navigation view
        view = CardNavigationView(ctx, cards, cards_db, rarities, info_type)
        embed = view.create_card_embed(0)

        if embed:
            message = await ctx.send(embed=embed, view=view)
            view.message = message

    @commands.command(name="mci", aliases=["mycardinfo", "myci"])
    async def my_card_info(self, ctx, *, card_name: str = None):
        """Show information about your specific card with current stats. Usage: ls mci <card_name> or ls mci all or ls mci <rarity>"""
        cards_db = load(CARDS_FILE)
        rarities = load(RARITIES_FILE)

        # Handle "all" case
        if card_name and card_name.lower() == "all":
            return await self._show_all_cards(ctx, cards_db, rarities, "owned")

        # Handle rarity case
        if card_name and card_name.upper() in rarities:
            return await self._show_rarity_cards(ctx, cards_db, rarities, card_name.upper(), "owned")

        if not card_name:
            embed = discord.Embed(
                title="❌ Missing Card Name",
                description="Usage: `ls mci <card_name>`\n\nExamples:\n• `ls mci Gun Park` (your specific card)\n• `ls mci all` (show all your cards)\n• `ls mci SR` (show your Super Rare cards)\n• `ls mci UR` (show your Ultra Rare cards)",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        users = load(USERS_FILE)
        user = ensure_user(users, str(ctx.author.id))
        save(USERS_FILE, users)

        user_cards = user.get("cards", [])

        # Find owned card (fuzzy search)
        owned_card = None
        search_lower = card_name.lower()

        # Exact match first
        for c in user_cards:
            if c.get('name', '').lower() == search_lower:
                owned_card = c
                break

        # Partial match if no exact match
        if not owned_card:
            matches = [c for c in user_cards if search_lower in c.get(
                'name', '').lower()]
            if len(matches) >= 1:
                # Show all matching cards one by one with navigation
                view = CardNavigationView(
                    ctx, matches, cards_db, rarities, "owned", show_evo_buttons=True)
                embed = view.create_card_embed(0)

                if embed:
                    message = await ctx.send(embed=embed, view=view)
                    view.message = message
                return
            else:
                embed = discord.Embed(
                    title="❌ Card Not Owned",
                    description=f"You don't own any card matching: **{card_name}**\n\nUse `ls inv` to see your cards or `ls mci all` to see all your cards.",
                    color=0xE74C3C
                )
                return await ctx.send(embed=embed)

        if not owned_card:
            embed = discord.Embed(
                title="❌ Card Not Owned",
                description=f"You don't own any card matching: **{card_name}**\n\nUse `ls inv` to see your cards or `ls mci all` to see all your cards.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # Create navigation view with evolution buttons for specific card lookup
        view = CardNavigationView(
            ctx, [owned_card], cards_db, rarities, "owned", show_evo_buttons=True)
        embed = view.create_card_embed(0)

        if embed:
            message = await ctx.send(embed=embed, view=view)
            view.message = message

    @commands.command(name="inv", aliases=["inventory", "cards"])
    async def inventory(self, ctx):
        users = load(USERS_FILE)
        user = ensure_user(users, str(ctx.author.id))
        save(USERS_FILE, users)
        cards = user.get("cards", [])
        tickets = user.get("tickets", {})
        chests = user.get("chests", {})
        equipment = user.get("equipment", {})
        emojis = load_emojis()

        # Check if inventory is completely empty
        has_items = len(cards) > 0 or any(tickets.values()) or any(
            chests.values()) or any(equipment.values())

        if not has_items:
            embed = discord.Embed(
                title="📦 Empty Inventory",
                description="You have no items yet!\n\nUse `ls pull` to get characters and items.",
                color=0x95A5A6
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        # Create comprehensive inventory embed
        embed = discord.Embed(
            title=f"📦 {ctx.author.display_name}'s Complete Inventory",
            color=0x5865F2
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)

        # Cards section
        if cards:
            rarity_count = {}
            for c in cards:
                rar = c.get('rarity', 'Common')
                rarity_count[rar] = rarity_count.get(rar, 0) + 1

            rarity_text = "\n".join(
                [f"• **{rar}:** `{count}`" for rar, count in sorted(rarity_count.items())])
            embed.add_field(
                name="🎴 Cards", value=f"**Total:** `{len(cards)}`\n{rarity_text}", inline=False)

        # Tickets section
        if tickets and any(tickets.values()):
            bosses = load("data/bosses.json")
            ticket_lines = []
            for ticket_id, count in tickets.items():
                if count > 0:
                    # Get boss name from ticket ID
                    boss_name = ticket_id.replace(
                        '_ticket', '').replace('_', ' ').title()

                    # Try to get actual boss name from bosses.json
                    found_boss = False
                    for boss_key, boss_info in bosses.items():
                        if f"{boss_info.get('name', '').lower().replace(' ', '_')}_ticket" == ticket_id:
                            boss_name = boss_info.get('name', boss_name)
                            found_boss = True
                            break

                    # If no boss found and name is "Unknown" or empty, use a better fallback
                    if not found_boss or boss_name in ["Unknown", ""]:
                        # Clean up the ticket ID for display
                        clean_name = ticket_id.replace(
                            '_ticket', '').replace('_', ' ').title()
                        boss_name = f"{clean_name} (Boss)"

                    # Get emoji for this ticket
                    ticket_emoji = emojis.get(ticket_id, "🎫")
                    ticket_lines.append(
                        f"{ticket_emoji} **{boss_name}** ×`{count}`")

            if ticket_lines:
                embed.add_field(name="🎫 Boss Tickets", value="\n".join(
                    ticket_lines[:10]), inline=False)

        # Chests section
        if chests and any(chests.values()):
            chest_lines = []
            for chest_id, count in chests.items():
                if count > 0:
                    chest_emoji = emojis.get(chest_id, "📦")
                    chest_name = chest_id.replace('_', ' ').title()
                    chest_lines.append(
                        f"{chest_emoji} **{chest_name}** ×`{count}`")

            if chest_lines:
                embed.add_field(name="📦 Chests", value="\n".join(
                    chest_lines), inline=False)

        # Equipment section
        if equipment and any(equipment.values()):
            weapons = load(WEAPONS_FILE)
            equip_lines = []
            for item_id, count in equipment.items():
                if count > 0:
                    weapon = weapons.get(item_id)
                    if weapon:
                        item_emoji = emojis.get(item_id, "⚔️")
                        equip_lines.append(
                            f"{item_emoji} **{weapon['name']}** ×`{count}`")

            if equip_lines:
                embed.add_field(name="⚔️ Equipment", value="\n".join(
                    equip_lines), inline=False)

        embed.set_footer(
            text="Use specific commands to manage different inventory types!")
        await ctx.send(embed=embed)

    @commands.command(name="finv", aliases=["fragments", "fragment", "shards"])
    async def fragment_inventory(self, ctx):
        """Interactive fragment inventory with rarity selector. Usage: ls finv"""
        users = load(USERS_FILE)
        user = ensure_user(users, str(ctx.author.id))
        save(USERS_FILE, users)
        fragments = user.get("fragments", {})

        if not fragments or all(count == 0 for count in fragments.values()):
            embed = discord.Embed(
                title="💎 Fragment Inventory",
                description="You have no fragments yet!\n\nGet fragments by pulling duplicate characters.",
                color=0x95A5A6
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            embed.set_footer(text="Fragments are used for character upgrades!")
            return await ctx.send(embed=embed)

        # Filter out zero fragments and sort by count
        active_fragments = {name: count for name,
                            count in fragments.items() if count > 0}
        sorted_fragments = sorted(
            active_fragments.items(), key=lambda x: x[1], reverse=True)

        # Load data
        rarities = load(RARITIES_FILE)
        cards_db = load(CARDS_FILE)
        emojis = load_emojis()

        # Group fragments by rarity code
        fragments_by_rarity = {}
        for name, count in sorted_fragments:
            card = next((c for c in cards_db.values()
                        if c.get('name') == name), None)
            if not card:
                continue
            rarity_code = card.get('rarity', 'C')
            if rarity_code not in fragments_by_rarity:
                fragments_by_rarity[rarity_code] = []
            fragments_by_rarity[rarity_code].append((name, count))

        if not fragments_by_rarity:
            embed = discord.Embed(
                title="💎 Fragment Inventory",
                description="You have fragments, but I couldn't match them to any cards.",
                color=0xE74C3C
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            return await ctx.send(embed=embed)

        # Build base embed
        embed = discord.Embed(
            title=f"💎 {ctx.author.display_name}'s Fragment Inventory",
            description=(
                f"**Total Fragments:** `{sum(active_fragments.values())}`\n"
                f"**Unique Characters:** `{len(active_fragments)}`\n\n"
                "Select a rarity from the menu below to view its fragments."
            ),
            color=0x9B59B6
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)

        # Build select options per rarity
        options = []
        for rarity_code, frag_list in sorted(fragments_by_rarity.items(), key=lambda x: x[0], reverse=True):
            rarity_info = rarities.get(rarity_code, {})
            rarity_display = rarity_info.get("display_name", rarity_code)
            rarity_emoji = rarity_info.get("emoji", "⭐")
            total_fragments = sum(count for _, count in frag_list)
            options.append(discord.SelectOption(
                label=f"{rarity_display}",
                description=f"{total_fragments} fragments • {len(frag_list)} characters",
                emoji=rarity_emoji if isinstance(rarity_emoji, str) else None,
                value=rarity_code
            ))

        # Define select for rarity filtering
        class FragmentRaritySelect(Select):

            def __init__(self, owner_id, fragments_by_rarity, rarities, emojis):
                super().__init__(
                    placeholder="Select a rarity to view its fragments...",
                    min_values=1,
                    max_values=1,
                    options=options
                )
                self.owner_id = owner_id
                self.fragments_by_rarity = fragments_by_rarity
                self.rarities = rarities
                self.emojis = emojis

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.owner_id:
                    await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
                    return

                rarity_code = self.values[0]
                frag_list = self.fragments_by_rarity.get(rarity_code, [])
                rarity_info = self.rarities.get(rarity_code, {})
                rarity_display = rarity_info.get("display_name", rarity_code)
                rarity_emoji = rarity_info.get("emoji", "⭐")

                # Build fragment lines with placeholder emojis per character
                lines = []
                for name, count in frag_list[:15]:
                    # placeholder; replace in emoji.json later
                    char_emoji = self.emojis.get(name) or "🧩"
                    lines.append(f"• {char_emoji} **{name}:** `{count}`")
                if len(frag_list) > 15:
                    lines.append(f"*...and {len(frag_list) - 15} more*")

                desc = "\n".join(
                    lines) if lines else "No fragments for this rarity."

                rarity_embed = discord.Embed(
                    title=f"💎 Fragments — {rarity_display}",
                    description=desc,
                    color=0x9B59B6
                )
                rarity_embed.set_author(
                    name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
                rarity_embed.set_footer(
                    text="Edit emoji.json to add custom emojis for each character.")

                await interaction.response.edit_message(embed=rarity_embed, view=self.view)

        view = View(timeout=120)
        view.add_item(FragmentRaritySelect(
            ctx.author.id, fragments_by_rarity, rarities, emojis))

        await ctx.send(embed=embed, view=view)

    @commands.command(name="equip")
    async def equip(self, ctx, card_name: str = None, item_name: str = None):
        if not card_name or not item_name:
            embed = discord.Embed(
                title="❌ Missing Arguments",
                description="Usage: `ls equip <card_name> <item_name>`\n\nExample: `ls equip Daniel Park Knife`",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        users = load(USERS_FILE)
        uid = str(ctx.author.id)
        user = ensure_user(users, uid)
        save(USERS_FILE, users)

        # 1. Find Card (Simple Search)
        target_card = None
        for c in user.get("cards", []):
            if card_name.lower() in c['name'].lower():
                target_card = c
                break

        if not target_card:
            embed = discord.Embed(
                title="❌ Card Not Found",
                description=f"Could not find card: **{card_name}**\n\nUse `ls inv` to see your cards.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # 2. Find Item in Inventory
        weapons = load(WEAPONS_FILE)
        item_id = None
        for wid, w in weapons.items():
            if item_name.lower() in w['name'].lower():
                item_id = wid
                break

        if not item_id:
            embed = discord.Embed(
                title="❌ Item Not Found",
                description=f"Could not find item: **{item_name}**",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        inv = user.get("equipment", {})
        if inv.get(item_id, 0) < 1:
            embed = discord.Embed(
                title="❌ Item Not Owned",
                description=f"You don't own **{weapons[item_id]['name']}**!\n\nGet items from raid drops.",
                color=0xE74C3C
            )
            return await ctx.send(embed=embed)

        # 3. Equip Logic
        old_item_name = None
        if target_card.get("equipped_item_id"):
            old = target_card["equipped_item_id"]
            old_item_name = weapons.get(old, {}).get('name', 'Unknown')
            inv[old] = inv.get(old, 0) + 1  # Return old item

        target_card["equipped_item_id"] = item_id
        inv[item_id] -= 1

        save(USERS_FILE, users)

        embed = discord.Embed(
            title="✅ Equipment Updated",
            description=f"**{weapons[item_id]['name']}** has been equipped to **{target_card['name']}**!",
            color=0x2ECC71
        )
        if old_item_name:
            embed.add_field(name="Previous Equipment",
                            value=f"`{old_item_name}` (returned to inventory)", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="profile", aliases=["p", "stats"])
    async def profile(self, ctx):
        users = load(USERS_FILE)
        user = ensure_user(users, str(ctx.author.id))
        save(USERS_FILE, users)

        wins = user.get("wins", 0)
        streak = user.get("streak", 0)
        yen = user.get("yen", 0)
        cards_count = len(user.get("cards", []))
        pulls = user.get("pulls", 0)

        embed = discord.Embed(
            title=f"👤 {ctx.author.display_name}'s Profile",
            color=0x5865F2
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        embed.add_field(
            name="⚔️ Combat",
            value=f"🏆 **Wins:** `{wins}`\n🔥 **Streak:** `{streak}`",
            inline=True
        )

        embed.add_field(
            name="💰 Economy",
            value=f"💴 **Yen:** `{yen:,}`\n🃏 **Pulls:** `{pulls}/12`",
            inline=True
        )

        embed.add_field(
            name="📦 Collection",
            value=f"🎴 **Cards:** `{cards_count}`",
            inline=True
        )

        embed.add_field(
            name="👥 Gang",
            value=user.get("gang_name", "None"),
            inline=True
        )

        await ctx.send(embed=embed)

    @commands.command(name="tickets", aliases=["ticket"])
    async def ticket_inventory(self, ctx):
        """View your boss tickets. Usage: ls tickets or ls ticket"""
        users = load(USERS_FILE)
        user = ensure_user(users, str(ctx.author.id))
        save(USERS_FILE, users)

        tickets = user.get("tickets", {})

        if not tickets or all(count == 0 for count in tickets.values()):
            embed = discord.Embed(
                title="🎫 Ticket Inventory",
                description="You have no tickets yet!\n\nGet tickets from `ls pull` (2.5% chance).",
                color=0x95A5A6
            )
            embed.set_author(name=ctx.author.display_name,
                             icon_url=ctx.author.display_avatar.url)
            embed.set_footer(
                text="Use tickets to create boss raids with `ls raid create <boss_name>`!")
            return await ctx.send(embed=embed)

        # Filter out zero tickets and sort by count
        active_tickets = {name: count for name,
                          count in tickets.items() if count > 0}
        sorted_tickets = sorted(active_tickets.items(),
                                key=lambda x: x[1], reverse=True)

        # Load bosses for display
        bosses = load("data/bosses.json")

        embed = discord.Embed(
            title=f"🎫 {ctx.author.display_name}'s Ticket Inventory",
            description=f"**Total Tickets:** `{sum(active_tickets.values())}`\n**Unique Boss Tickets:** `{len(active_tickets)}`",
            color=0xFFD700
        )
        embed.set_author(name=ctx.author.display_name,
                         icon_url=ctx.author.display_avatar.url)
        embed.set_footer(
            text="Use tickets to create boss raids with `ls raid create <boss_name>`!")

        # Group tickets by rarity/tier
        ticket_lines = []
        for ticket_id, count in sorted_tickets:
            # Get boss name from ticket ID
            boss_name = ticket_id.replace(
                '_ticket', '').replace('_', ' ').title()

            # Try to get actual boss name from bosses.json
            boss_data = None
            found_boss = False
            for boss_key, boss_info in bosses.items():
                if f"{boss_info.get('name', '').lower().replace(' ', '_')}_ticket" == ticket_id:
                    boss_name = boss_info.get('name', boss_name)
                    boss_data = boss_info
                    found_boss = True
                    break

            # If no boss found and name is "Unknown" or empty, use a better fallback
            if not found_boss or boss_name in ["Unknown", ""]:
                # Clean up the ticket ID for display
                clean_name = ticket_id.replace(
                    '_ticket', '').replace('_', ' ').title()
                boss_name = f"{clean_name} (Boss)"

            # Get boss image if available
            thumbnail_url = None
            if boss_data and boss_data.get('image'):
                thumbnail_url = boss_data['image']

            # Create ticket line
            line = f"🎫 **{boss_name}** ×`{count}`"
            ticket_lines.append(line)

            # Display tickets
        if ticket_lines:
            # Limit to 20 tickets
            ticket_text = "\n".join(ticket_lines[:20])
            if len(ticket_lines) > 20:
                ticket_text += f"\n*...and {len(ticket_lines) - 20} more*"

            embed.add_field(
                name="🎫 Boss Tickets",
                value=ticket_text,
                inline=False
            )

            # Add usage example
            embed.add_field(
                name="📖 How to Use",
                value="`ls raid create <boss_name>`\nExample: `ls raid create Gun Park`",
                inline=False
            )

            # Set thumbnail if we have a boss image (use first ticket's boss)
            if sorted_tickets and thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Info(bot))
