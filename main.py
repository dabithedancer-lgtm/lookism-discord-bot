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


@app.route('/health')
def health():
    return {"status": "healthy", "bot": "online"}


def run_flask():
    """Run Flask app in a way that doesn't block the event loop"""
    import os
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting Flask server on port {port}...")
    try:
        app.run(host='0.0.0.0', port=port, use_reloader=False, debug=False)
    except Exception as e:
        print(f"Flask server error: {e}")


def keep_alive():
    """Start Flask server in a separate daemon thread"""
    print("Starting keep-alive Flask server...")
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Keep-alive Flask server started in background thread")


# Enable Intents (Required for Pycord)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=config.PREFIXES,
                   intents=intents, help_command=None, case_insensitive=True)


async def load_extensions(bot):
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
    await load_extensions(bot)

    # Start the bot with retry logic
    max_retries = 5
    retry_delay = 30  # seconds

    try:
        for attempt in range(max_retries):
            try:
                await bot.start(config.TOKEN)
                break
            except discord.errors.HTTPException as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    print(
                        f"Rate limited. Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise e
    finally:
        # Properly close the bot session
        if not bot.is_closed():
            await bot.close()


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
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Failed to start bot: {e}")
        import traceback
        traceback.print_exc()
