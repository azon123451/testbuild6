import logging
from typing import Optional

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import settings
from .managers import ConversationManager, OperatorManager, OperatorStatus
from .storage import JsonStore


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

operators_store = JsonStore(
    settings.data_dir / "operators.json",
    {"operators": {}},
)
conversations_store = JsonStore(
    settings.data_dir / "conversations.json",
    {"conversations": {}},
)
operator_manager = OperatorManager(operators_store, settings.operators_allowlist)
conversation_manager = ConversationManager(conversations_store)


def operator_display_name(chat_id: int) -> str:
    try:
        operator = operator_manager.get_operator(chat_id)
    except KeyError:
        return str(chat_id)
    return operator.display_name or operator.username or str(chat_id)


def pick_operator_for_new_client() -> Optional[int]:
    candidates = []
    for operator in operator_manager.list_operators():
        if operator.status != OperatorStatus.AVAILABLE:
            continue
        load = len(conversation_manager.get_clients_for_operator(operator.chat_id))
        candidates.append((load, operator.updated_at, operator.chat_id))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return
    chat_id = message.chat_id
    user = update.effective_user
    if operator_manager.is_operator(chat_id):
        text = (
            "Вы уже зарегистрированы как оператор.\n"
            "Команды: /clients, /focus <id>, /reply <id> <сообщение>, "
            "/end <id>, /available, /busy, /offline."
        )
    else:
        name = user.full_name if user else "клиент"
        text = (
            f"Здравствуйте, {name}!\n"
            "Вы можете написать сюда любой вопрос, и ближайший свободный оператор ответит вам."
        )
    await message.reply_text(text)


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return
    chat_id = message.chat_id
    if not context.args:
        await message.reply_text("Использование: /register <секретное_слово>")
        return
    provided_secret = context.args[0]
    if provided_secret != settings.operator_secret:
        await message.reply_text("Неверное секретное слово.")
        return
    user = update.effective_user
    username = (user.username or "").lower() if user else ""
    display_name = user.full_name if user else username or str(chat_id)
    try:
        operator_manager.upsert_operator(chat_id, username, display_name)
        operator_manager.set_status(chat_id, OperatorStatus.AVAILABLE)
    except PermissionError as error:
        await message.reply_text(str(error))
        return
    await message.reply_text(
        "Готово! Вы добавлены как оператор. Используйте /available, когда готовы получать новые запросы."
    )
    logger.info("Operator %s registered", chat_id)


async def require_operator(update: Update) -> Optional[int]:
    message = update.effective_message
    if not message:
        return None
    chat_id = message.chat_id
    if not operator_manager.is_operator(chat_id):
        await message.reply_text(
            "Вы не зарегистрированы как оператор. Команда /register <секрет>."
        )
        return None
    return chat_id


async def set_status(
    update: Update, _: ContextTypes.DEFAULT_TYPE, status: OperatorStatus
) -> None:
    chat_id = await require_operator(update)
    if not chat_id:
        return
    operator_manager.set_status(chat_id, status)
    if status == OperatorStatus.AVAILABLE:
        text = "Статус: доступен для новых клиентов."
    elif status == OperatorStatus.BUSY:
        text = "Статус: занят (новые клиенты не назначаются автоматически)."
    else:
        text = "Статус: офлайн. На вас не будут назначаться клиенты."
    await update.effective_message.reply_text(text)


async def show_clients(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = await require_operator(update)
    if not chat_id:
        return
    clients = conversation_manager.get_clients_for_operator(chat_id)
    if not clients:
        await update.effective_message.reply_text("За вами сейчас нет активных клиентов.")
        return
    snapshot = conversation_manager.conversation_snapshot()
    lines = []
    for client_id in clients:
        record = snapshot.get(str(client_id), {})
        name = record.get("client_name", str(client_id))
        last = record.get("last_activity", "n/a")
        lines.append(f"{client_id}: {name} (последняя активность {last})")
    await update.effective_message.reply_text("\n".join(lines))


async def focus_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = await require_operator(update)
    if not chat_id:
        return
    if not context.args:
        await update.effective_message.reply_text("Использование: /focus <client_id>")
        return
    try:
        client_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("client_id должен быть числом.")
        return
    assigned_clients = conversation_manager.get_clients_for_operator(chat_id)
    if client_id not in assigned_clients:
        await update.effective_message.reply_text("Этот клиент не закреплен за вами.")
        return
    operator_manager.set_active_client(chat_id, client_id)
    await update.effective_message.reply_text(
        f"Активный клиент установлен: {client_id}. Теперь можно писать ему напрямую."
    )


async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = await require_operator(update)
    if not chat_id:
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Использование: /reply <client_id> <текст>")
        return
    try:
        client_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("client_id должен быть числом.")
        return
    text = " ".join(context.args[1:])
    record = conversation_manager.get_client_record(client_id)
    if not record or int(record["operator_id"]) != chat_id:
        await update.effective_message.reply_text(
            "Нельзя писать этому клиенту: он не закреплен за вами."
        )
        return
    await context.bot.send_message(
        chat_id=client_id,
        text=f"💬 {operator_display_name(chat_id)}: {text}",
    )
    await update.effective_message.reply_text("Сообщение отправлено клиенту.")


async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = await require_operator(update)
    if not chat_id:
        return
    if not context.args:
        await update.effective_message.reply_text("Использование: /end <client_id>")
        return
    try:
        client_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("client_id должен быть числом.")
        return
    record = conversation_manager.get_client_record(client_id)
    if not record or int(record["operator_id"]) != chat_id:
        await update.effective_message.reply_text("Этот клиент не найден среди ваших диалогов.")
        return
    conversation_manager.release_client(client_id)
    operator = operator_manager.get_operator(chat_id)
    if operator.active_client == client_id:
        operator_manager.set_active_client(chat_id, None)
    remaining_clients = conversation_manager.get_clients_for_operator(chat_id)
    if not remaining_clients and operator.status != OperatorStatus.OFFLINE:
        operator_manager.set_status(chat_id, OperatorStatus.AVAILABLE)
    await context.bot.send_message(
        chat_id=client_id,
        text="Диалог завершен. Если появятся дополнительные вопросы, напишите нам снова.",
    )
    await update.effective_message.reply_text("Диалог завершен и клиент освобожден.")


async def operator_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not operator_manager.is_operator(message.chat_id):
        return
    operator = operator_manager.get_operator(message.chat_id)
    if not operator.active_client:
        await message.reply_text(
            "Не выбран активный клиент. Используйте /focus <id> или /reply <id> <текст>."
        )
        return
    await relay_to_client(
        context=context,
        source_chat_id=message.chat_id,
        target_chat_id=operator.active_client,
        notice=f"💬 {operator.display_name}",
        message_id=message.message_id,
    )


async def relay_to_client(
    context: ContextTypes.DEFAULT_TYPE,
    source_chat_id: int,
    target_chat_id: int,
    notice: str,
    message_id: int,
) -> None:
    try:
        await context.bot.send_message(chat_id=target_chat_id, text=notice)
        await context.bot.copy_message(
            chat_id=target_chat_id,
            from_chat_id=source_chat_id,
            message_id=message_id,
        )
    except TelegramError as error:
        logger.error("Failed to relay message: %s", error)


async def client_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return
    chat_id = message.chat_id
    if operator_manager.is_operator(chat_id):
        return
    user = update.effective_user
    display_name = user.full_name if user else str(chat_id)
    operator_chat_id = conversation_manager.get_operator_for_client(chat_id)
    new_assignment = False
    if not operator_chat_id:
        operator_chat_id = pick_operator_for_new_client()
        if not operator_chat_id:
            await message.reply_text(
                "Все операторы офлайн. Мы обязательно ответим, как только кто-то подключится."
            )
            return
        conversation_manager.bind_client(chat_id, operator_chat_id, display_name)
        operator_manager.set_status(operator_chat_id, OperatorStatus.BUSY)
        assigned_operator = operator_manager.get_operator(operator_chat_id)
        if not assigned_operator.active_client:
            operator_manager.set_active_client(operator_chat_id, chat_id)
        new_assignment = True
    if new_assignment:
        await context.bot.send_message(
            chat_id=operator_chat_id,
            text=(
                f"🆕 Новый клиент {display_name} ({chat_id}). "
                f"Команда /focus {chat_id} или /reply {chat_id} <текст>."
            ),
        )
        await message.reply_text("Мы подключили оператора, ожидайте ответа.")
    await relay_to_operator(update, context, operator_chat_id, display_name)


async def relay_to_operator(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    operator_chat_id: int,
    client_name: str,
) -> None:
    message = update.effective_message
    if not message:
        return
    notice = f"📨 {client_name}"
    try:
        await context.bot.send_message(chat_id=operator_chat_id, text=notice)
        await context.bot.copy_message(
            chat_id=operator_chat_id,
            from_chat_id=message.chat_id,
            message_id=message.message_id,
        )
    except TelegramError as error:
        logger.error("Failed to deliver client message: %s", error)
        await message.reply_text(
            "Не удалось связаться с оператором. Попробуйте еще раз чуть позже."
        )


async def status_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = await require_operator(update)
    if not chat_id:
        return
    operator = operator_manager.get_operator(chat_id)
    clients = conversation_manager.get_clients_for_operator(chat_id)
    text = (
        f"Статус: {operator.status.value}\n"
        f"Активный клиент: {operator.active_client or 'не выбран'}\n"
        f"Текущие клиенты: {', '.join(map(str, clients)) or 'нет'}"
    )
    await update.effective_message.reply_text(text)


async def route_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return
    chat_id = message.chat_id
    if operator_manager.is_operator(chat_id):
        await operator_message(update, context)
    else:
        await client_message(update, context)


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("available", lambda u, c: set_status(u, c, OperatorStatus.AVAILABLE)))
    app.add_handler(CommandHandler("busy", lambda u, c: set_status(u, c, OperatorStatus.BUSY)))
    app.add_handler(
        CommandHandler("offline", lambda u, c: set_status(u, c, OperatorStatus.OFFLINE))
    )
    app.add_handler(CommandHandler("clients", show_clients))
    app.add_handler(CommandHandler("focus", focus_client))
    app.add_handler(CommandHandler("reply", reply_command))
    app.add_handler(CommandHandler("end", end_chat))
    app.add_handler(CommandHandler("status", status_command))
    relay_filter = filters.ALL & ~filters.COMMAND
    app.add_handler(MessageHandler(relay_filter, route_message))


def build_application() -> Application:
    return ApplicationBuilder().token(settings.token).build()


def main() -> None:
    application = build_application()
    register_handlers(application)
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

