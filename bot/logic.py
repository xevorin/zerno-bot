"""Бизнес-логика бота без aiogram и сети: меню, корзина, время выдачи, тексты.

Всё здесь — чистые функции, поэтому модуль целиком покрыт тестами в tests/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

PICKUP_OPTIONS: tuple[int, ...] = (10, 20, 30)
MAX_QTY = 10
ORDER_NUMBER_OFFSET = 100

Cart = dict[str, int]


# ---------- меню ----------

@dataclass(frozen=True)
class Item:
    id: str
    title: str
    price: int
    category: str


@dataclass(frozen=True)
class Category:
    id: str
    title: str
    items: tuple[Item, ...]


@dataclass(frozen=True)
class Menu:
    shop: str
    categories: tuple[Category, ...]

    def category(self, category_id: str) -> Category | None:
        return next((c for c in self.categories if c.id == category_id), None)

    def item(self, item_id: str) -> Item | None:
        for category in self.categories:
            for item in category.items:
                if item.id == item_id:
                    return item
        return None


def parse_menu(data: dict) -> Menu:
    """Собирает Menu из словаря menu.json и проверяет его."""
    seen: set[str] = set()
    categories = []
    for raw_cat in data["categories"]:
        items = []
        for raw in raw_cat["items"]:
            item_id = str(raw["id"])
            price = raw["price"]
            if item_id in seen:
                raise ValueError(f"Повторяется id позиции: {item_id}")
            if not isinstance(price, int) or price <= 0:
                raise ValueError(f"Цена {item_id} должна быть целым числом больше нуля")
            seen.add(item_id)
            items.append(Item(item_id, str(raw["title"]), price, str(raw_cat["id"])))
        if not items:
            raise ValueError(f"Пустая категория: {raw_cat['id']}")
        categories.append(Category(str(raw_cat["id"]), str(raw_cat["title"]), tuple(items)))
    return Menu(str(data.get("shop", "Зерно")), tuple(categories))


def load_menu(path: str | Path) -> Menu:
    with open(path, encoding="utf-8") as f:
        return parse_menu(json.load(f))


# ---------- корзина ----------

@dataclass(frozen=True)
class CartLine:
    item: Item
    qty: int

    @property
    def amount(self) -> int:
        return self.item.price * self.qty


def clamp_qty(qty: int) -> int:
    return max(1, min(MAX_QTY, qty))


def add_to_cart(cart: Cart, item_id: str, qty: int) -> Cart:
    """Возвращает новую корзину; одной позиции не больше MAX_QTY штук."""
    if qty < 1:
        raise ValueError("Количество должно быть не меньше 1")
    new_cart = dict(cart)
    new_cart[item_id] = min(MAX_QTY, new_cart.get(item_id, 0) + qty)
    return new_cart


def cart_lines(menu: Menu, cart: Cart) -> list[CartLine]:
    """Строки корзины в порядке меню; позиции, которых нет в меню, пропускаются."""
    lines = []
    for category in menu.categories:
        for item in category.items:
            qty = cart.get(item.id, 0)
            if qty > 0:
                lines.append(CartLine(item, qty))
    return lines


def cart_total(menu: Menu, cart: Cart) -> int:
    return sum(line.amount for line in cart_lines(menu, cart))


def cart_count(menu: Menu, cart: Cart) -> int:
    return sum(line.qty for line in cart_lines(menu, cart))


# ---------- время и номер ----------

def pickup_at(now: datetime, minutes: int) -> datetime:
    if minutes not in PICKUP_OPTIONS:
        raise ValueError(f"Недопустимое время выдачи: {minutes}")
    return (now + timedelta(minutes=minutes)).replace(second=0, microsecond=0)


def format_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def order_number(row_id: int) -> int:
    """Номер для клиента: id строки в БД плюс смещение, чтобы первый заказ был №101."""
    return row_id + ORDER_NUMBER_OFFSET


def format_price(rub: int) -> str:
    return f"{rub:,}".replace(",", " ") + " ₽"


# ---------- тексты ----------

GREETING = (
    "Привет! Это бот кофейни «Зерно».\n"
    "Соберите заказ кнопками, а мы приготовим его к вашему приходу.\n\n"
    "Выберите раздел меню:"
)
MENU_PROMPT = "Выберите раздел меню:"
PICKUP_QUESTION = "Когда заберёте заказ?"
EMPTY_CART = "Корзина пуста. Загляните в меню."
CANCEL_TEXT = "Корзина очищена. Чтобы начать заново, нажмите /start."
STAFF_DONE_SUFFIX = "\n\nСтатус: готов, клиент получил уведомление."


def item_button(item: Item) -> str:
    return f"{item.title} · {format_price(item.price)}"


def category_text(category: Category) -> str:
    return f"<b>{escape(category.title)}</b>\nВыберите позицию:"


def item_text(item: Item, qty: int) -> str:
    return (
        f"<b>{escape(item.title)}</b>\n"
        f"Цена: {format_price(item.price)}\n\n"
        f"Количество: {qty}\n"
        f"Сумма: {format_price(item.price * qty)}"
    )


def _lines_block(menu: Menu, cart: Cart) -> str:
    return "\n".join(
        f"{escape(line.item.title)} × {line.qty} — {format_price(line.amount)}"
        for line in cart_lines(menu, cart)
    )


def added_text(menu: Menu, item: Item, qty: int, cart: Cart) -> str:
    return (
        f"Добавил в корзину: {escape(item.title)} × {qty}.\n"
        f"В корзине {cart_count(menu, cart)} шт. на {format_price(cart_total(menu, cart))}"
    )


def cart_text(menu: Menu, cart: Cart) -> str:
    if not cart_lines(menu, cart):
        return EMPTY_CART
    return (
        f"<b>Корзина</b>\n{_lines_block(menu, cart)}\n\n"
        f"Итого: <b>{format_price(cart_total(menu, cart))}</b>"
    )


def confirm_text(menu: Menu, cart: Cart, minutes: int, ready_at: datetime) -> str:
    return (
        f"<b>Проверьте заказ</b>\n{_lines_block(menu, cart)}\n\n"
        f"Итого: <b>{format_price(cart_total(menu, cart))}</b>\n"
        f"Заберёте через {minutes} мин, к {format_time(ready_at)}.\n"
        "Оплата на кассе при получении."
    )


def order_accepted_text(number: int, total: int, ready_at: datetime) -> str:
    return (
        f"<b>Заказ №{number} принят</b>\n"
        f"Сумма: {format_price(total)}\n"
        f"Будет готов в {format_time(ready_at)}"
    )


def staff_order_text(number: int, menu: Menu, cart: Cart, ready_at: datetime, customer: str) -> str:
    return (
        f"<b>Новый заказ №{number}</b>\n"
        f"Клиент: {escape(customer)}\n"
        f"Выдать к {format_time(ready_at)}\n\n"
        f"{_lines_block(menu, cart)}\n\n"
        f"Итого: {format_price(cart_total(menu, cart))}"
    )


def order_ready_text(number: int) -> str:
    return f"Заказ №{number} готов, заберите на кассе."
