import os
import yaml
from dotenv import load_dotenv

load_dotenv()

# Charge fichier YAML
with open("config.yml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

# Secrets et connexions
TOKEN = os.getenv("TELEGRAM_TOKEN")
DB_PATH = os.getenv("DB_PATH", "sqlite:///db.sqlite3")

# IDs Telegram
SUPER_GROUP = int(cfg["super_group"])
ADMINS = set(cfg["admin_ids"])
MENTORS = set(cfg.get("mentor_ids", []))
TOPICS = cfg["topics"]
BOT_USERNAME = "@be_trezv_bot"   # sans espace


# Constantes métier
AVG_HOURS_DAY = cfg.get("avg_hours_day", 5)
AVG_COST_DAY = cfg.get("avg_cost_day", 5)
AVG_NEURONS_DAY = cfg.get("avg_neurons_day", 10000)
MILESTONES = cfg.get("milestones", [7, 30, 60, 90, 100, 180, 365])

# paiement et essai gratuit 90J
TRIAL_DAYS    = 90
GRACE_DAYS    = 2
FOUNDERS_CAP  = 100
TRIBUTE_URL_TEMPLATE = "https://t.me/tribute/app?startapp=swg0"