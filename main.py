import discord
import os
import config
import asyncio
from discord.ext import commands

# Enable Intents (Required for Pycord)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=config.PREFIXES,
                   intents=intents, help_command=None, case_insensitive=True)


async def main():
    # Ensure data folder exists
    if not os.path.exists("./data"):
        os.makedirs("./data")
        print("Created ./data directory")

    # Load all Cogs
    initial_extensions = [
        'cogs.admin',
        'cogs.economy',
        'cogs.gatcha',  # Fixed: filename is gatcha.py
        'cogs.info',
        'cogs.raid',
        'cogs.gang',
        'cogs.crew',  # Crew system (max 4 crews)
        'cogs.leaderboard',
        'cogs.help',
        'cogs.combat'  # Restored PvP
    ]

    # Load cogs
    for extension in initial_extensions:
        try:
            await bot.load_extension(extension)
            print(f"Loaded {extension}")
        except Exception as e:
            print(f"Failed to load {extension}: {e}")

    await bot.start(config.TOKEN)


@bot.event
async def on_ready():
    print(f"Bot Online as {bot.user}")
    await bot.change_presence(activity=discord.Game(name="ls help | Lookism Gacha"))

if __name__ == "__main__":
    asyncio.run(main())
