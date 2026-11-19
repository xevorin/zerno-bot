"""Настройки из переменных окружения (или файла .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    bot_token: str
    staff_chat_id: int
    db_path: Path
    menu_path: Path
    timezone: str


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    token = os.getenv("BOT_TOKEN", "").strip()
    staff = os.getenv("STAFF_CHAT_ID", "").strip()
    if not token:
        raise RuntimeError("Не задан BOT_TOKEN: скопируйте .env.example в .env и впишите токен от @BotFather")
    try:
        staff_chat_id = int(staff)
    except ValueError:
        raise RuntimeError("STAFF_CHAT_ID должен быть числом, например -1001234567890") from None
    return Settings(
        bot_token=token,
        staff_chat_id=staff_chat_id,
        db_path=ROOT / os.getenv("DB_PATH", "data/orders.db"),
        menu_path=ROOT / os.getenv("MENU_PATH", "data/menu.json"),
        timezone=os.getenv("TZ_NAME", "Europe/Moscow"),
    )
