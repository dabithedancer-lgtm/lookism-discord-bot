import discord
import os
import config
import asyncio
import sys
import platform
from discord.ext import commands
from flask import Flask
from threading import Thread

# Flask web server for keeping bot alive
app = Flask('')


@app.route('/')
def home():
    return "Bot is running!"


def run_flask():
    """Run Flask app in a way that doesn't block the event loop"""
    app.run(host='0.0.0.0', port=8080, use_reloader=False, debug=False)


def keep_alive():
    """Start Flask server in a separate daemon thread"""
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()


# Enable Intents (Required for Pycord)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=config.PREFIXES,
                   intents=intents, help_command=None, case_insensitive=True)


async def load_extensions():
    """Load all cogs asynchronously"""
    # Ensure data folder exists
    if not os.path.exists("./data"):
        os.makedirs("./data")
        print("Created ./data directory")

    # Load all Cogs
    initial_extensions = [
        'cogs.admin',
        'cogs.economy',
        'cogs.gatcha',
        'cogs.info',
        'cogs.raid',
        'cogs.gang',
        'cogs.crew',  # Crew system (max 4 crews)
        'cogs.leaderboard',
        'cogs.help',
        'cogs.combat',  # Restored PvP
        'cogs.patreon'  # Patreon system
    ]

    # Load cogs
    for extension in initial_extensions:
        try:
            await bot.load_extension(extension)
            print(f"Loaded {extension}")
        except Exception as e:
            print(f"Failed to load {extension}: {e}")


async def main():
    # Load extensions first
    await load_extensions()

    # Start the bot
    await bot.start(config.TOKEN)


@bot.event
async def on_ready():
    print(f"Bot Online as {bot.user}")
    await bot.change_presence(activity=discord.Game(name="ls help | Lookism Gacha"))


if __name__ == "__main__":
    # Set up the event loop policy for Windows
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Start Flask in a separate thread
    keep_alive()

    # Run the async main function
    asyncio.run(main())
