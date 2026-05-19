from __future__ import annotations

import json
import logging
from urllib import error as urllib_error
from urllib import request as urllib_request

from apps.core.selectors import get_telegram_settings

logger = logging.getLogger(__name__)


class TelegramDispatchError(RuntimeError):
    pass


def _send_telegram_message(*, token: str, chat_id: str, text: str) -> dict[str, object]:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    request = urllib_request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=8) as response:  # noqa: S310
            raw_body = response.read().decode("utf-8")
    except (urllib_error.URLError, TimeoutError, OSError) as exc:
        raise TelegramDispatchError(f"Telegram network error: {exc}") from exc

    try:
        body = json.loads(raw_body)
    except ValueError as exc:
        raise TelegramDispatchError("Telegram returned malformed JSON.") from exc
    if not bool(body.get("ok")):
        description = str(body.get("description") or "Unknown Telegram API error.")
        raise TelegramDispatchError(description)
    return body


def _status_label_ru(status: str) -> str:
    labels = {
        "new": "Новый",
        "processing": "В обработке",
        "ready_for_shipment": "Готов к отправке",
        "shipped": "Отправлен",
        "completed": "Завершен",
        "cancelled": "Отменен",
    }
    return labels.get(str(status or "").strip(), str(status or "").strip())


def _return_status_label_ru(status: str) -> str:
    labels = {
        "new": "Новая заявка",
        "approved": "Одобрено",
        "rejected": "Отказано",
        "awaiting_ttn": "Ожидаем ТТН",
        "in_transit": "В пути",
        "received": "Получено",
        "accepted": "Принято",
        "refunded": "Возврат",
        "cancelled": "Отменено",
    }
    return labels.get(str(status or "").strip(), str(status or "").strip())


def send_ops_order_status_notification(*, order_number: str, from_status: str, to_status: str, actor_name: str) -> None:
    settings = get_telegram_settings()
    if not settings.is_enabled or not settings.ops_enabled or not settings.ops_notify_order_status:
        return
    token = str(settings.ops_bot_token or "").strip()
    chat_id = str(settings.ops_chat_id or "").strip()
    if not token or not chat_id:
        return
    text = (
        f"Заказ #{order_number}\n"
        f"Статус: {_status_label_ru(from_status)} -> {_status_label_ru(to_status)}\n"
        f"Сотрудник: {actor_name or '-'}"
    )
    try:
        _send_telegram_message(token=token, chat_id=chat_id, text=text)
    except TelegramDispatchError as exc:
        logger.warning("Telegram ops order status notification failed: %s", exc)


def send_ops_waybill_notification(*, action: str, order_number: str, waybill_number: str) -> None:
    settings = get_telegram_settings()
    if not settings.is_enabled or not settings.ops_enabled:
        return
    action_key = str(action or "").strip().lower()
    if action_key == "created" and not settings.ops_notify_waybill_created:
        return
    if action_key == "updated" and not settings.ops_notify_waybill_updated:
        return
    if action_key == "deleted" and not settings.ops_notify_waybill_deleted:
        return

    token = str(settings.ops_bot_token or "").strip()
    chat_id = str(settings.ops_chat_id or "").strip()
    if not token or not chat_id:
        return

    action_label = {
        "created": "создана",
        "updated": "изменена",
        "deleted": "удалена",
    }.get(action_key, action_key)
    text = (
        f"ТТН {action_label}\n"
        f"Заказ: #{order_number}\n"
        f"Номер ТТН: {waybill_number or '-'}"
    )
    try:
        _send_telegram_message(token=token, chat_id=chat_id, text=text)
    except TelegramDispatchError as exc:
        logger.warning("Telegram ops waybill notification failed: %s", exc)


def send_ops_order_created_notification(*, order_number: str) -> None:
    settings = get_telegram_settings()
    if not settings.is_enabled or not settings.ops_enabled:
        return
    token = str(settings.ops_bot_token or "").strip()
    chat_id = str(settings.ops_chat_id or "").strip()
    if not token or not chat_id:
        return
    text = (
        "Новый заказ\n"
        f"Заказ: #{order_number}"
    )
    try:
        _send_telegram_message(token=token, chat_id=chat_id, text=text)
    except TelegramDispatchError as exc:
        logger.warning("Telegram ops order created notification failed: %s", exc)


def send_ops_order_deleted_notification(*, order_number: str, actor_name: str) -> None:
    settings = get_telegram_settings()
    if not settings.is_enabled or not settings.ops_enabled:
        return
    token = str(settings.ops_bot_token or "").strip()
    chat_id = str(settings.ops_chat_id or "").strip()
    if not token or not chat_id:
        return
    text = (
        "Заказ удален\n"
        f"Заказ: #{order_number}\n"
        f"Сотрудник: {actor_name or '-'}"
    )
    try:
        _send_telegram_message(token=token, chat_id=chat_id, text=text)
    except TelegramDispatchError as exc:
        logger.warning("Telegram ops order deleted notification failed: %s", exc)


def send_ops_return_created_notification(*, return_number: str, order_number: str, actor_name: str) -> None:
    settings = get_telegram_settings()
    if not settings.is_enabled or not settings.ops_enabled or not settings.ops_notify_return_created:
        return
    token = str(settings.ops_bot_token or "").strip()
    chat_id = str(settings.ops_chat_id or "").strip()
    if not token or not chat_id:
        return
    text = (
        "Новый возврат\n"
        f"Возврат: {return_number}\n"
        f"Заказ: #{order_number}\n"
        f"Клиент: {actor_name or '-'}"
    )
    try:
        _send_telegram_message(token=token, chat_id=chat_id, text=text)
    except TelegramDispatchError as exc:
        logger.warning("Telegram ops return created notification failed: %s", exc)


def send_ops_return_status_notification(*, return_number: str, from_status: str, to_status: str, actor_name: str) -> None:
    settings = get_telegram_settings()
    if not settings.is_enabled or not settings.ops_enabled or not settings.ops_notify_return_status:
        return
    token = str(settings.ops_bot_token or "").strip()
    chat_id = str(settings.ops_chat_id or "").strip()
    if not token or not chat_id:
        return
    text = (
        f"Возврат {return_number}\n"
        f"Статус: {_return_status_label_ru(from_status)} -> {_return_status_label_ru(to_status)}\n"
        f"Сотрудник: {actor_name or '-'}"
    )
    try:
        _send_telegram_message(token=token, chat_id=chat_id, text=text)
    except TelegramDispatchError as exc:
        logger.warning("Telegram ops return status notification failed: %s", exc)


def send_telegram_test_message(*, bot_kind: str, text: str) -> dict[str, object]:
    settings = get_telegram_settings()
    kind = str(bot_kind or "").strip().lower()
    if kind == "ops":
        token = str(settings.ops_bot_token or "").strip()
        chat_id = str(settings.ops_chat_id or "").strip()
    elif kind == "support":
        token = str(settings.support_bot_token or "").strip()
        chat_id = str(settings.support_chat_id or "").strip()
    elif kind == "system":
        token = str(settings.system_bot_token or "").strip()
        chat_id = str(settings.system_chat_id or "").strip()
    else:
        raise TelegramDispatchError("Unsupported bot kind.")

    if not token or not chat_id:
        raise TelegramDispatchError("Token and chat_id are required.")
    return _send_telegram_message(token=token, chat_id=chat_id, text=text)
