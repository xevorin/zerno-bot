from datetime import datetime
from pathlib import Path

import pytest

from bot import logic

MENU_PATH = Path(__file__).resolve().parent.parent / "data" / "menu.json"


@pytest.fixture(scope="module")
def menu() -> logic.Menu:
    return logic.load_menu(MENU_PATH)


def test_menu_has_three_categories(menu):
    assert [c.title for c in menu.categories] == ["Кофе", "Не кофе", "Выпечка"]
    assert sum(len(c.items) for c in menu.categories) >= 10


def test_menu_lookup(menu):
    assert menu.item("latte").price == 210
    assert menu.item("latte").category == "coffee"
    assert menu.item("nope") is None
    assert menu.category("bakery").title == "Выпечка"


def test_parse_menu_rejects_duplicate_ids():
    data = {"categories": [{"id": "a", "title": "A", "items": [
        {"id": "x", "title": "X", "price": 1}, {"id": "x", "title": "Y", "price": 2}]}]}
    with pytest.raises(ValueError):
        logic.parse_menu(data)


def test_parse_menu_rejects_bad_price():
    data = {"categories": [{"id": "a", "title": "A", "items": [{"id": "x", "title": "X", "price": 0}]}]}
    with pytest.raises(ValueError):
        logic.parse_menu(data)


def test_add_to_cart_is_immutable_and_sums():
    cart = {}
    cart2 = logic.add_to_cart(cart, "latte", 2)
    cart3 = logic.add_to_cart(cart2, "latte", 1)
    assert cart == {}
    assert cart2 == {"latte": 2}
    assert cart3 == {"latte": 3}


def test_add_to_cart_caps_and_validates():
    assert logic.add_to_cart({"latte": 9}, "latte", 5) == {"latte": logic.MAX_QTY}
    with pytest.raises(ValueError):
        logic.add_to_cart({}, "latte", 0)


def test_clamp_qty():
    assert logic.clamp_qty(0) == 1
    assert logic.clamp_qty(4) == 4
    assert logic.clamp_qty(99) == logic.MAX_QTY


def test_cart_total_and_count(menu):
    cart = {"cappuccino": 1, "croissant": 1}
    assert logic.cart_total(menu, cart) == 340
    assert logic.cart_count(menu, cart) == 2


def test_cart_ignores_unknown_items(menu):
    cart = {"latte": 2, "removed-item": 5}
    assert logic.cart_total(menu, cart) == 420
    assert [line.item.id for line in logic.cart_lines(menu, cart)] == ["latte"]


def test_cart_lines_follow_menu_order(menu):
    cart = {"croissant": 1, "espresso": 2}
    assert [line.item.id for line in logic.cart_lines(menu, cart)] == ["espresso", "croissant"]


@pytest.mark.parametrize(("minutes", "expected"), [(10, "08:42"), (20, "08:52"), (30, "09:02")])
def test_pickup_at(minutes, expected):
    now = datetime(2026, 11, 19, 8, 32, 47)
    assert logic.format_time(logic.pickup_at(now, minutes)) == expected


def test_pickup_crosses_midnight():
    now = datetime(2026, 11, 19, 23, 55)
    ready = logic.pickup_at(now, 10)
    assert logic.format_time(ready) == "00:05"
    assert ready.day == 20


def test_pickup_rejects_unknown_option():
    with pytest.raises(ValueError):
        logic.pickup_at(datetime(2026, 1, 1, 9, 0), 15)


def test_order_number():
    assert logic.order_number(1) == 101
    assert logic.order_number(48) == 148


def test_format_price():
    assert logic.format_price(190) == "190 ₽"
    assert logic.format_price(1240) == "1 240 ₽"


def test_cart_text(menu):
    text = logic.cart_text(menu, {"cappuccino": 1, "croissant": 2})
    assert "Капучино 0,3 × 1 — 190 ₽" in text
    assert "Круассан × 2 — 300 ₽" in text
    assert "Итого: <b>490 ₽</b>" in text
    assert logic.cart_text(menu, {}) == logic.EMPTY_CART


def test_order_accepted_text():
    text = logic.order_accepted_text(148, 340, datetime(2026, 11, 19, 8, 42))
    assert text == "<b>Заказ №148 принят</b>\nСумма: 340 ₽\nБудет готов в 08:42"


def test_staff_text_escapes_customer(menu):
    text = logic.staff_order_text(101, menu, {"latte": 1}, datetime(2026, 1, 1, 9, 10), "<Аня>")
    assert "Новый заказ №101" in text
    assert "&lt;Аня&gt;" in text
    assert "Выдать к 09:10" in text


def test_order_ready_text():
    assert logic.order_ready_text(148) == "Заказ №148 готов, заберите на кассе."
