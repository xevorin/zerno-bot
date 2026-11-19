"""Inline-клавиатуры и callback data."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.logic import MAX_QTY, PICKUP_OPTIONS, Category, Item, Menu, item_button


class CategoryCb(CallbackData, prefix="cat"):
    id: str


class ItemCb(CallbackData, prefix="item"):
    id: str
    qty: int = 1


class AddCb(CallbackData, prefix="add"):
    id: str
    qty: int


class NavCb(CallbackData, prefix="nav"):
    to: str  # menu | cart | clear | checkout | confirm


class TimeCb(CallbackData, prefix="time"):
    minutes: int


class ReadyCb(CallbackData, prefix="ready"):
    number: int


def categories_kb(menu: Menu) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for category in menu.categories:
        kb.button(text=category.title, callback_data=CategoryCb(id=category.id))
    kb.button(text="Корзина", callback_data=NavCb(to="cart"))
    kb.adjust(len(menu.categories), 1)
    return kb.as_markup()


def items_kb(category: Category) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in category.items:
        kb.button(text=item_button(item), callback_data=ItemCb(id=item.id))
    kb.button(text="← Меню", callback_data=NavCb(to="menu"))
    kb.button(text="Корзина", callback_data=NavCb(to="cart"))
    kb.adjust(*([1] * len(category.items)), 2)
    return kb.as_markup()


def qty_kb(item: Item, qty: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="−", callback_data=ItemCb(id=item.id, qty=max(1, qty - 1)))
    kb.button(text=str(qty), callback_data=ItemCb(id=item.id, qty=qty))
    kb.button(text="+", callback_data=ItemCb(id=item.id, qty=min(MAX_QTY, qty + 1)))
    kb.button(text="В корзину", callback_data=AddCb(id=item.id, qty=qty))
    kb.button(text="← Назад", callback_data=CategoryCb(id=item.category))
    kb.adjust(3, 1, 1)
    return kb.as_markup()


def after_add_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Добавить ещё", callback_data=NavCb(to="menu"))
    kb.button(text="Корзина", callback_data=NavCb(to="cart"))
    kb.adjust(2)
    return kb.as_markup()


def cart_kb(has_items: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if has_items:
        kb.button(text="Оформить", callback_data=NavCb(to="checkout"))
        kb.button(text="Очистить", callback_data=NavCb(to="clear"))
    kb.button(text="← Меню", callback_data=NavCb(to="menu"))
    kb.adjust(2, 1) if has_items else kb.adjust(1)
    return kb.as_markup()


def pickup_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for minutes in PICKUP_OPTIONS:
        kb.button(text=f"Через {minutes} мин", callback_data=TimeCb(minutes=minutes))
    kb.button(text="← Корзина", callback_data=NavCb(to="cart"))
    kb.adjust(len(PICKUP_OPTIONS), 1)
    return kb.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Подтвердить", callback_data=NavCb(to="confirm"))
    kb.button(text="Изменить время", callback_data=NavCb(to="checkout"))
    kb.adjust(1, 1)
    return kb.as_markup()


def staff_kb(number: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Готово", callback_data=ReadyCb(number=number))
    return kb.as_markup()
