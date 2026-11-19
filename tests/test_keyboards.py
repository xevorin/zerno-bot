from pathlib import Path

from bot import keyboards as kb
from bot import logic

MENU = logic.load_menu(Path(__file__).resolve().parent.parent / "data" / "menu.json")


def _buttons(markup):
    return [b for row in markup.inline_keyboard for b in row]


def test_callback_data_fits_telegram_limit():
    for category in MENU.categories:
        for item in category.items:
            for cb in (kb.ItemCb(id=item.id, qty=10), kb.AddCb(id=item.id, qty=10)):
                assert len(cb.pack().encode()) <= 64


def test_categories_kb_has_cart():
    texts = [b.text for b in _buttons(kb.categories_kb(MENU))]
    assert texts == ["Кофе", "Не кофе", "Выпечка", "Корзина"]


def test_pickup_kb_options():
    texts = [b.text for b in _buttons(kb.pickup_kb())]
    assert texts[:3] == ["Через 10 мин", "Через 20 мин", "Через 30 мин"]


def test_staff_kb_roundtrip():
    button = _buttons(kb.staff_kb(148))[0]
    assert button.text == "Готово"
    assert kb.ReadyCb.unpack(button.callback_data).number == 148


def test_router_imports():
    from bot.handlers import router

    assert router.name == "orders"
