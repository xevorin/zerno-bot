import asyncio
from datetime import datetime

from bot.db import OrderStore


def test_create_and_mark_ready(tmp_path):
    async def scenario():
        store = OrderStore(tmp_path / "orders.db")
        await store.init()
        args = dict(
            user_id=1, chat_id=555, customer="Аня", cart={"latte": 2}, total=420,
            pickup_at=datetime(2026, 11, 19, 8, 42), created_at=datetime(2026, 11, 19, 8, 32),
        )
        first = await store.create_order(**args)
        second = await store.create_order(**args)
        assert (first, second) == (101, 102)
        assert await store.get_status(first) == "new"

        assert await store.mark_ready(first) == 555
        assert await store.get_status(first) == "ready"
        # повторное нажатие «Готово» не шлёт второе уведомление
        assert await store.mark_ready(first) is None
        assert await store.mark_ready(999) is None

    asyncio.run(scenario())
