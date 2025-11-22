from __future__ import annotations

import asyncio
import logging
import os
from collections import deque

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage

# ─────────────── НАСТРОЙКИ ───────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("Необходимо указать токен бота в переменной окружения BOT_TOKEN")


def _parse_operator_ids(env_value: str | None) -> list[int]:
    """Преобразует строку вида '111,222,333' в список ID операторов."""
    if not env_value:
        return []

    operator_ids: list[int] = []
    for chunk in env_value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            operator_ids.append(int(chunk))
        except ValueError:
            logging.warning("Пропущен оператор с некорректным ID: %s", chunk)
    return operator_ids


OPERATORS = _parse_operator_ids(os.getenv("OPERATORS"))
if not OPERATORS:
    logging.warning("Список операторов пуст. Укажите переменную окружения OPERATORS.")

DB_PATH = os.getenv("DB_PATH", "support_bot.db")


# ─────────────── БАЗА И ОЧЕРЕДЬ ───────────────
queue: deque[int] = deque()          # очередь client_id
busy_operators: dict[int, int] = {}  # {operator_id: client_id}
client_operator: dict[int, int] = {}  # {client_id: operator_id}


# ─────────────── ЗАПУСК ───────────────
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
logging.basicConfig(level=logging.INFO)


# ─────────────── БАЗА (история сообщений) ───────────────
async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                text TEXT,
                from_operator BOOLEAN,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


# ─────────────── СТАРТ ДЛЯ КЛИЕНТА ───────────────
@dp.message(Command("start"))
async def start_client(message: Message) -> None:
    if message.from_user.id in OPERATORS:
        await message.answer(
            "Привет, оператор! 👋\n"
            "Как только появится клиент — ты увидишь кнопку «Взять в работу»."
        )
        return

    client_id = message.from_user.id

    if client_id in client_operator or client_id in queue:
        await message.answer("Ты уже в очереди или общаешься с оператором 😊")
        return

    queue.append(client_id)
    position = len(queue)

    await message.answer(
        "Привет! 👋\n"
        "Ты в очереди на консультацию.\n"
        f"Твоя позиция: <b>{position}</b>\n"
        "Ожидай, скоро с тобой свяжется менеджер.",
        protect_content=True,
    )

    # Уведомляем всех свободных операторов
    await notify_free_operators()


# ─────────────── УВЕДОМЛЕНИЕ ОПЕРАТОРОВ О НОВОМ КЛИЕНТЕ ───────────────
async def notify_free_operators() -> None:
    if not queue:
        return

    for op_id in OPERATORS:
        if op_id not in busy_operators:
            try:
                client_id = queue[0]
                client = await bot.get_chat(client_id)
                name = client.full_name
                username = f"@{client.username}" if client.username else "нет"

                keyboard = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="Взять клиента в работу 🚀",
                                callback_data=f"take_{client_id}",
                            )
                        ]
                    ]
                )

                await bot.send_message(
                    op_id,
                    "🔔 Новый клиент в очереди!\n\n"
                    f"Имя: {name}\n"
                    f"Username: {username}\n"
                    f"ID: {client_id}\n"
                    f"В очереди: {len(queue)} чел.",
                    reply_markup=keyboard,
                )
            except Exception as exc:
                logging.warning("Не удалось уведомить оператора %s: %s", op_id, exc)


# ─────────────── ОПЕРАТОР ВЗЯЛ КЛИЕНТА ───────────────
@dp.callback_query(F.data.startswith("take_"))
async def take_client(callback: types.CallbackQuery) -> None:
    if callback.from_user.id not in OPERATORS:
        await callback.answer("Ты не оператор!")
        return

    client_id = int(callback.data.split("_")[1])

    if client_id not in queue:
        await callback.answer("Клиент уже взят другим оператором")
        return

    # Убираем из очереди
    queue.remove(client_id)
    operator_id = callback.from_user.id
    busy_operators[operator_id] = client_id
    client_operator[client_id] = operator_id

    await callback.message.edit_text(f"Ты взял клиента {client_id} ✅")

    # Уведомляем клиента
    await bot.send_message(
        client_id,
        "Менеджер подключился! Задавай свой вопрос 😊",
        protect_content=True,
    )

    # Показываем оператору историю (если есть)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT from_operator, text FROM messages WHERE client_id = ? ORDER BY id",
            (client_id,),
        ) as cursor:
            history = await cursor.fetchall()
            if history:
                await callback.message.answer("📋 История переписки с клиентом:")
                for is_op, text in history:
                    prefix = "Оператор" if is_op else "Клиент"
                    await callback.message.answer(f"<b>{prefix}:</b> {text}", parse_mode="HTML")

    # Обновляем очередь
    await update_queue_positions()
    await notify_free_operators()


# ─────────────── СООБЩЕНИЯ ОТ КЛИЕНТА ───────────────
@dp.message(F.chat.type == "private", ~Command("start"))
async def from_client(message: Message) -> None:
    client_id = message.from_user.id

    if client_id in OPERATORS:
        return  # операторы отдельно ниже

    if client_id not in client_operator and client_id not in queue:
        await message.answer("Нажми /start, чтобы начать общение")
        return

    # Если в очереди — просто подтверждаем
    if client_id in queue:
        position = list(queue).index(client_id) + 1
        await message.answer(
            f"Сообщение принято! Ты {position}-й в очереди.",
            protect_content=True,
        )
        return

    # Если уже есть оператор — пересылаем ему
    operator_id = client_operator.get(client_id)
    if operator_id:
        await bot.copy_message(
            chat_id=operator_id,
            from_chat_id=client_id,
            message_id=message.message_id,
            caption=f"💬 Сообщение от клиента {client_id}",
        )

        # Сохраняем в базу
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO messages (client_id, text, from_operator) VALUES (?, ?, 0)",
                (client_id, message.text or "[медиа]"),
            )
            await db.commit()


# ─────────────── СООБЩЕНИЯ ОТ ОПЕРАТОРА (ответ на пересланное) ───────────────
@dp.message(F.reply_to_message & F.from_user.id.in_(OPERATORS))
async def from_operator_reply(message: Message) -> None:
    if message.from_user.id not in busy_operators:
        return

    client_id = busy_operators[message.from_user.id]

    await bot.copy_message(
        chat_id=client_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        protect_content=True,
    )

    # Сохраняем
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (client_id, text, from_operator) VALUES (?, ?, 1)",
            (client_id, message.text or "[медиа]"),
        )
        await db.commit()


# ─────────────── ОБНОВЛЕНИЕ ПОЗИЦИЙ В ОЧЕРЕДИ ───────────────
async def update_queue_positions() -> None:
    for idx, client_id in enumerate(queue, 1):
        try:
            await bot.send_message(
                client_id,
                f"Ты в очереди. Позиция: <b>{idx}</b>",
                protect_content=True,
            )
        except Exception as exc:
            logging.warning("Не удалось отправить сообщение клиенту %s: %s", client_id, exc)


# ─────────────── ЗАПУСК ───────────────
async def main() -> None:
    await init_db()
    logging.info("Бот поддержки запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

