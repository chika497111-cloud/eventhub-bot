import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: list[int] = [
    int(uid.strip())
    for uid in os.getenv("ADMIN_ID", "").split(",")
    if uid.strip().isdigit()
]

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env")
