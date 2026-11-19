"""Обработчики команд и кнопок.

menu, store и settings приходят из workflow data диспетчера (см. main.py).
Корзина живёт в FSM-хранилище: state.data["cart"] = {item_id: qty}.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot import keyboards as kb
from bot import logic
from bot.config import Settings
from bot.db import OrderStore
from bot.logic import Menu

router = Router(name="orders")


async def _edit(call: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    # Telegram отвечает ошибкой, если текст и кнопки не изменились; это не страшно.
    with suppress(TelegramBadRequest):
        await call.message.edit_text(text, reply_markup=markup)


async def _cart(state: FSMContext) -> logic.Cart:
    return dict((await state.get_data()).get("cart", {}))


def _now(settings: Settings) -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, menu: Menu) -> None:
    await state.clear()
    await message.answer(logic.GREETING, reply_markup=kb.categories_kb(menu))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(logic.CANCEL_TEXT)


@router.callback_query(kb.CategoryCb.filter())
async def on_category(call: CallbackQuery, callback_data: kb.CategoryCb, menu: Menu) -> None:
    category = menu.category(callback_data.id)
    if category is None:
        await call.answer("Раздел не найден", show_alert=True)
        return
    await _edit(call, logic.category_text(category), kb.items_kb(category))
    await call.answer()


@router.callback_query(kb.ItemCb.filter())
async def on_item(call: CallbackQuery, callback_data: kb.ItemCb, menu: Menu) -> None:
    item = menu.item(callback_data.id)
    if item is None:
        await call.answer("Позиции уже нет в меню", show_alert=True)
        return
    qty = logic.clamp_qty(callback_data.qty)
    await _edit(call, logic.item_text(item, qty), kb.qty_kb(item, qty))
    await call.answer()


@router.callback_query(kb.AddCb.filter())
async def on_add(call: CallbackQuery, callback_data: kb.AddCb, state: FSMContext, menu: Menu) -> None:
    item = menu.item(callback_data.id)
    if item is None:
        await call.answer("Позиции уже нет в меню", show_alert=True)
        return
    qty = logic.clamp_qty(callback_data.qty)
    cart = logic.add_to_cart(await _cart(state), item.id, qty)
    await state.update_data(cart=cart)
    await _edit(call, logic.added_text(menu, item, qty, cart), kb.after_add_kb())
    await call.answer("Добавлено")


@router.callback_query(kb.NavCb.filter(F.to == "menu"))
async def on_menu(call: CallbackQuery, menu: Menu) -> None:
    await _edit(call, logic.MENU_PROMPT, kb.categories_kb(menu))
    await call.answer()


@router.callback_query(kb.NavCb.filter(F.to == "cart"))
async def on_cart(call: CallbackQuery, state: FSMContext, menu: Menu) -> None:
    cart = await _cart(state)
    has_items = bool(logic.cart_lines(menu, cart))
    await _edit(call, logic.cart_text(menu, cart), kb.cart_kb(has_items))
    await call.answer()


@router.callback_query(kb.NavCb.filter(F.to == "clear"))
async def on_clear(call: CallbackQuery, state: FSMContext, menu: Menu) -> None:
    await state.update_data(cart={}, minutes=None)
    await _edit(call, logic.EMPTY_CART, kb.cart_kb(False))
    await call.answer("Корзина очищена")


@router.callback_query(kb.NavCb.filter(F.to == "checkout"))
async def on_checkout(call: CallbackQuery, state: FSMContext, menu: Menu) -> None:
    if not logic.cart_lines(menu, await _cart(state)):
        await call.answer(logic.EMPTY_CART, show_alert=True)
        return
    await _edit(call, logic.PICKUP_QUESTION, kb.pickup_kb())
    await call.answer()


@router.callback_query(kb.TimeCb.filter())
async def on_time(
    call: CallbackQuery, callback_data: kb.TimeCb, state: FSMContext, menu: Menu, settings: Settings
) -> None:
    cart = await _cart(state)
    if not logic.cart_lines(menu, cart):
        await call.answer(logic.EMPTY_CART, show_alert=True)
        return
    try:
        ready_at = logic.pickup_at(_now(settings), callback_data.minutes)
    except ValueError:
        await call.answer("Выберите время из списка", show_alert=True)
        return
    await state.update_data(minutes=callback_data.minutes)
    await _edit(call, logic.confirm_text(menu, cart, callback_data.minutes, ready_at), kb.confirm_kb())
    await call.answer()


@router.callback_query(kb.NavCb.filter(F.to == "confirm"))
async def on_confirm(
    call: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    menu: Menu,
    store: OrderStore,
    settings: Settings,
) -> None:
    data = await state.get_data()
    cart = dict(data.get("cart", {}))
    minutes = data.get("minutes")
    if not logic.cart_lines(menu, cart) or minutes is None:
        await call.answer("Заказ устарел, начните заново: /start", show_alert=True)
        return

    now = _now(settings)
    ready_at = logic.pickup_at(now, minutes)
    total = logic.cart_total(menu, cart)
    customer = call.from_user.full_name
    if call.from_user.username:
        customer += f" (@{call.from_user.username})"

    number = await store.create_order(
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        customer=customer,
        cart=cart,
        total=total,
        pickup_at=ready_at,
        created_at=now,
    )
    await state.clear()
    await _edit(call, logic.order_accepted_text(number, total, ready_at))
    await call.answer("Заказ отправлен")
    await bot.send_message(
        settings.staff_chat_id,
        logic.staff_order_text(number, menu, cart, ready_at, customer),
        reply_markup=kb.staff_kb(number),
    )


@router.callback_query(kb.ReadyCb.filter())
async def on_ready(call: CallbackQuery, callback_data: kb.ReadyCb, bot: Bot, store: OrderStore) -> None:
    chat_id = await store.mark_ready(callback_data.number)
    if chat_id is None:
        await call.answer("Этот заказ уже отмечен", show_alert=True)
        return
    await bot.send_message(chat_id, logic.order_ready_text(callback_data.number))
    await _edit(call, call.message.html_text + logic.STAFF_DONE_SUFFIX)
    await call.answer("Клиент получил уведомление")
