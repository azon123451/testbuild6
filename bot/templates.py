def client_connected(client_name: str) -> str:
    return f"🧑 Клиент {client_name} подключён к вам. Напишите ответ, чтобы начать."


def queued_message(queue_position: int | None) -> str:
    base = "Все операторы заняты, поставили вас в очередь."
    if queue_position:
        return f"{base} Позиция: {queue_position}."
    return base


def operator_busy() -> str:
    return "Вы уже обрабатываете максимум чатов. Завершите текущий диалог командой /done."


def session_closed() -> str:
    return "Диалог закрыт. Клиент получил финальное уведомление."


def notify_new_client(client_name: str, client_id: int, text: str) -> str:
    return f"Новое сообщение от клиента {client_name} (ID {client_id}):\n{text}"

