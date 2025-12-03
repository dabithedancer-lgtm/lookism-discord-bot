import time
import config
from utils.database import load

WEAPONS_FILE = "data/weapons.json"


def compute_stats(card_data, level, aura, equipped_item_id=None):
    # Base Stats
    stats = card_data.get('stats', {}).get(
        'evo_1', {'attack': 10, 'health': 100, 'speed': 10})
    base_atk = stats.get('attack', 10)
    base_hp = stats.get('health', 100)
    base_spd = stats.get('speed', 10)

    # Multipliers
    lvl_mult = 1 + ((level - 1) * 0.0025)
    aura_mult = 1 + (aura * (2.0 / 100000))
    total_mult = lvl_mult * aura_mult

    final_atk = int(base_atk * total_mult)
    final_hp = int(base_hp * total_mult)
    final_spd = int(base_spd * total_mult)

    # Equipment Bonus
    if equipped_item_id:
        weapons = load(WEAPONS_FILE)
        item = weapons.get(equipped_item_id)
        if item:
            final_atk += item['stats'].get('attack', 0)
            final_hp += item['stats'].get('health', 0)
            final_spd += item['stats'].get('speed', 0)

    return {"attack": final_atk, "health": final_hp, "speed": final_spd}


def regenerate_pulls(user):
    now = int(time.time())
    last = user.get("last_pull_regen_ts", now)
    max_pulls = user.get("max_pulls", config.MAX_PULLS)
    curr = user.get("pulls", max_pulls)

    if curr >= max_pulls:
        user["last_pull_regen_ts"] = now
        return user

    diff = now - last
    gained = diff // config.PULL_REGEN_SECONDS

    if gained > 0:
        new_p = min(max_pulls, curr + gained)
        user["pulls"] = new_p
        if new_p >= max_pulls:
            user["last_pull_regen_ts"] = now
        else:
            user["last_pull_regen_ts"] += (gained * config.PULL_REGEN_SECONDS)
    return user
