# config.py
import os
from dotenv import load_dotenv

# Load environment variables from token.env file
load_dotenv('token.env')

# Read token from environment variables
TOKEN = os.getenv('DISCORD_TOKEN')
print(f"Token loaded: {TOKEN[:10]}..." if TOKEN else "Token not found")

if not TOKEN:
    print("Token not found")
    raise ValueError("DISCORD_TOKEN not found in environment variables!")

PREFIXES = [
    "ls ", "ls",      # lower
    "LS ", "LS",      # upper
    "Ls ", "Ls",      # capital L, lower s
    "lS ", "lS",      # lower l, capital S
]
ADMINS = [1315746066900975770]  # Your User ID

# Constants
MAX_PULLS = 12
PULL_REGEN_SECONDS = 900
DAILY_COOLDOWN = 86400
GANG_CREATE_COST = 150000
MINE_COOLDOWN = 14400  # 4 hours

# URLs (Placeholders - Replace with your actual URLs)
IMG_SUMMON_ORB = "https://media.tenor.com/2RoDo8pZt6wAAAAC/black-clover-mobile-summon.gif"
IMG_TERRITORY_MAP = "https://example.com/map.jpg"

# Patreon Role IDs
PATREON_ROLES = [
    1444532012424888454,  # Copy Tier
    1444532053776535676,  # UI Tier
    1444532102338052216   # TUI Tier
]

# File Paths
DATA_DIR = "./data"
