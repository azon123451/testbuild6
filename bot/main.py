import asyncio
import logging
from typing import Dict, Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from shared.enums import MessageSender
from shared.schemas import MessageCreate

from .config import get_settings
from .faq import FAQResponder
from .history_client import HistoryClient
from .operators import OperatorManager, OperatorState
from .queue import QueueManager
from .sessions import SessionRegistry
from . import templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

bot = Bot(token=settings.telegram_bot_token, parse_mode="HTML")
dp = Dispatcher()

operator_manager = OperatorManager(set(settings.operator_pins), settings.operator_max_concurrent)
session_registry = SessionRegistry()
queue_manager = QueueManager()
faq_responder = FAQResponder(
    {
        "когда приедет курьер": "Стандартное время доставки — 1-2 часа. Оператор уточнит детали в чате.",
        "где мой заказ": "Оператор проверит статус заказа в системе и вернётся к вам в ближайшее время.",
        "какие способы оплаты": "Мы принимаем оплату картой, наличными курьеру и онлайн-оплату в приложении.",
    }
)
history_client = HistoryClient(settings.backend_base_url, settings.backend_api_token)

client_profiles: Dict[int, str] = {}


async def log_message(client_id: int, operator_id: Optional[int], sender: MessageSender, text: str):
    payload = MessageCreate(
        client_telegram_id=client_id,
        operator_telegram_id=operator_id,
        sender=sender,
        text=text,
    )
    try:
        await history_client.log_message(payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to log message: %s", exc)


async def close_session_history(client_id: int):
    try:
        await history_client.close_session(client_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to close session: %s", exc)


async def attach_client_to_operator(client_id: int, operator_state: OperatorState):
    session_registry.bind(client_id, operator_state.telegram_id)
    operator_manager.assign_client(operator_state.telegram_id, client_id)
    client_name = client_profiles.get(client_id, f"ID {client_id}")
    await bot.send_message(
        operator_state.telegram_id,
        templates.client_connected(client_name),
        protect_content=True,
    )
    await bot.send_message(
        operator_state.telegram_id,
        f"Первое сообщение от клиента:\n{client_name} ({client_id})",
        protect_content=True,
    )
    await bot.send_message(
        client_id,
        "Соединили с оператором. Ответ придёт в ближайшее время ✅",
        protect_content=True,
    )


async def pull_from_queue(operator_state: OperatorState):
    while operator_state.is_available:
        next_client = queue_manager.dequeue()
        if not next_client:
            break
        await attach_client_to_operator(next_client, operator_state)


@dp.message(Command("start"))
async def start_cmd(message: Message):
    if message.chat.type != "private":
        return
    client_profiles[message.from_user.id] = message.from_user.full_name or message.from_user.username or "Клиент"
    await message.answer(
        "Здравствуйте! Мы передадим сообщение оператору магазина. Напишите ваш вопрос.",
        protect_content=True,
    )


@dp.message(Command("operator"))
async def operator_login(message: Message, command: CommandObject):
    pin = (command.args or "").strip()
    if not pin:
        await message.answer("Используйте: /operator <PIN>")
        return
    try:
        state = operator_manager.authenticate(message.from_user.id, message.from_user.full_name, pin)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await message.answer(
        f"Добро пожаловать, {state.full_name}! Активных клиентов: {len(state.active_clients)}. "
        f"В очереди: {len(queue_manager)}.",
        protect_content=True,
    )
    await pull_from_queue(state)


@dp.message(Command("me"))
async def operator_status(message: Message):
    if not operator_manager.is_operator(message.from_user.id):
        return
    state = operator_manager.get(message.from_user.id)
    clients = ", ".join(str(cid) for cid in session_registry.get_clients_for_operator(state.telegram_id)) or "нет"
    active = session_registry.get_active_client(state.telegram_id)
    await message.answer(
        f"Вы онлайн. Активный клиент: {active or 'не выбран'}. Все клиенты: {clients}. "
        f"Очередь: {len(queue_manager)}.",
        protect_content=True,
    )


@dp.message(Command("use"))
async def operator_set_active(message: Message, command: CommandObject):
    if not operator_manager.is_operator(message.from_user.id):
        return
    if not command.args:
        await message.answer("Укажите ID клиента: /use <client_id>")
        return
    try:
        client_id = int(command.args.strip())
    except ValueError:
        await message.answer("ID клиента должен быть числом.")
        return
    if not session_registry.set_active_client(message.from_user.id, client_id):
        await message.answer("Этот клиент не закреплён за вами.")
        return
    await message.answer(f"Активный клиент переключён на {client_id}.", protect_content=True)


@dp.message(Command("done"))
async def operator_finish(message: Message, command: CommandObject):
    if not operator_manager.is_operator(message.from_user.id):
        return
    client_id: Optional[int] = None
    if command.args:
        try:
            client_id = int(command.args.strip())
        except ValueError:
            await message.answer("ID клиента должен быть числом.")
            return
    if client_id is None:
        client_id = session_registry.get_active_client(message.from_user.id)
    if client_id is None:
        await message.answer("Нет активного клиента.", protect_content=True)
        return
    operator_id = session_registry.release(client_id)
    operator_manager.release_client(message.from_user.id, client_id)
    await close_session_history(client_id)
    await bot.send_message(
        client_id,
        "Оператор завершил диалог. Если возникнут новые вопросы — просто напишите снова!",
        protect_content=True,
    )
    await message.answer(templates.session_closed(), protect_content=True)
    state = operator_manager.get(operator_id)
    if state:
        await pull_from_queue(state)


@dp.message(Command("next"))
async def operator_take_next(message: Message):
    if not operator_manager.is_operator(message.from_user.id):
        return
    state = operator_manager.get(message.from_user.id)
    if not state.is_available:
        await message.answer(templates.operator_busy(), protect_content=True)
        return
    next_client = queue_manager.dequeue()
    if not next_client:
        await message.answer("Очередь пустая.", protect_content=True)
        return
    await attach_client_to_operator(next_client, state)


@dp.message(F.chat.type == "private", F.text)
async def process_text(message: Message):
    user_id = message.from_user.id
    client_profiles[user_id] = message.from_user.full_name or message.from_user.username or "Пользователь"
    if operator_manager.is_operator(user_id):
        await process_operator_text(message)
    else:
        await process_client_text(message)


async def process_client_text(message: Message):
    client_id = message.from_user.id
    operator_id = session_registry.get_operator(client_id)
    operator_state: Optional[OperatorState] = None
    if operator_id:
        operator_state = operator_manager.get(operator_id)
        if not operator_state:
            session_registry.release(client_id)
            operator_id = None

    if not operator_state:
        operator_state = operator_manager.pick_available()
        if operator_state:
            queue_manager.remove(client_id)
            await attach_client_to_operator(client_id, operator_state)
        else:
            queue_manager.enqueue(client_id)
            auto_text = f"{settings.auto_reply_text}\n{templates.queued_message(len(queue_manager))}"
            await message.answer(auto_text, protect_content=True)
            faq_answer = faq_responder.find_answer(message.text)
            if faq_answer:
                await message.answer(f"Быстрый ответ: {faq_answer}", protect_content=True)
            await log_message(client_id, None, MessageSender.CLIENT, message.text)
            return

    operator_state.touch()
    await bot.send_message(
        operator_state.telegram_id,
        templates.notify_new_client(message.from_user.full_name, client_id, message.text),
        protect_content=True,
    )
    session_registry.set_active_client(operator_state.telegram_id, client_id)
    await log_message(client_id, operator_state.telegram_id, MessageSender.CLIENT, message.text)


async def process_operator_text(message: Message):
    operator_id = message.from_user.id
    client_id = session_registry.get_active_client(operator_id)
    if not client_id:
        await message.answer("Нет активного клиента. Используйте /next или /use <id>.", protect_content=True)
        return
    await bot.send_message(
        client_id,
        message.text,
        protect_content=True,
    )
    await log_message(client_id, operator_id, MessageSender.OPERATOR, message.text)


async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await history_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())

