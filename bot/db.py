"""Хранение заказов в SQLite через aiosqlite."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import aiosqlite

from bot.logic import Cart, order_number

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    chat_id    INTEGER NOT NULL,
    customer   TEXT    NOT NULL,
    items      TEXT    NOT NULL,
    total      INTEGER NOT NULL,
    pickup_at  TEXT    NOT NULL,
    status     TEXT    NOT NULL DEFAULT 'new',
    created_at TEXT    NOT NULL
)
"""


class OrderStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)

    async def init(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(SCHEMA)
            await db.commit()

    async def create_order(
        self,
        *,
        user_id: int,
        chat_id: int,
        customer: str,
        cart: Cart,
        total: int,
        pickup_at: datetime,
        created_at: datetime,
    ) -> int:
        """Сохраняет заказ и возвращает его номер для клиента."""
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "INSERT INTO orders (user_id, chat_id, customer, items, total, pickup_at, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    chat_id,
                    customer,
                    json.dumps(cart, ensure_ascii=False),
                    total,
                    pickup_at.isoformat(),
                    created_at.isoformat(),
                ),
            )
            await db.commit()
            return order_number(cursor.lastrowid)

    async def mark_ready(self, number: int) -> int | None:
        """Ставит статус «готов». Возвращает chat_id клиента или None, если заказ уже выдан или не найден."""
        row_id = number - order_number(0)
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "UPDATE orders SET status = 'ready' WHERE id = ? AND status = 'new'", (row_id,)
            )
            await db.commit()
            if cursor.rowcount == 0:
                return None
            async with db.execute("SELECT chat_id FROM orders WHERE id = ?", (row_id,)) as cur:
                row = await cur.fetchone()
            return row[0] if row else None

    async def get_status(self, number: int) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT status FROM orders WHERE id = ?", (number - order_number(0),)
            ) as cur:
                row = await cur.fetchone()
        return row[0] if row else None
