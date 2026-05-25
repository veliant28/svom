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


def _batch_stop_reason_label_ru(stop_reason: str) -> str:
    key = str(stop_reason or "").strip().lower()
    if key == "quota_or_remote_error":
        return "Квота исчерпана"
    if key == "manual_stop":
        return "Остановлен вручную"
    if key == "stale_timeout":
        return "Остановлен по таймауту"
    return stop_reason or "-"


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


def _get_system_channel_for_batch_notifications() -> tuple[str, str] | None:
    settings = get_telegram_settings()
    if not settings.is_enabled or not settings.system_enabled or not settings.system_notify_autodb_batch_status:
        return None
    token = str(settings.system_bot_token or "").strip()
    chat_id = str(settings.system_chat_id or "").strip()
    if not token or not chat_id:
        return None
    return token, chat_id


def send_system_autodb_batch_started_notification(
    *,
    run_id: str,
    actor_name: str,
    requested_limit: int,
    selected_products_count: int,
) -> None:
    channel = _get_system_channel_for_batch_notifications()
    if channel is None:
        return
    token, chat_id = channel
    text = (
        "AutoDB batch запущен\n"
        f"Run ID: {run_id}\n"
        f"Сотрудник: {actor_name or '-'}\n"
        f"Размер батча: {int(requested_limit)}"
    )
    try:
        _send_telegram_message(token=token, chat_id=chat_id, text=text)
    except TelegramDispatchError as exc:
        logger.warning("Telegram system AutoDB batch started notification failed: %s", exc)


def send_system_autodb_batch_progress_notification(
    *,
    run_id: str,
    processed: int,
    batch_size: int,
    linked: int,
    errors: int,
    quota_used: int,
    quota_limit: int,
    cycle_index: int = 0,
    cycle_processed: int | None = None,
    cycle_total: int | None = None,
) -> None:
    channel = _get_system_channel_for_batch_notifications()
    if channel is None:
        return
    token, chat_id = channel
    progress_current = int(cycle_processed) if cycle_processed is not None else int(processed)
    progress_total = int(cycle_total) if cycle_total is not None else max(int(batch_size or 0), 0)
    cycle_line = f"Цикл: {int(cycle_index)}\n" if int(cycle_index or 0) > 0 else ""
    text = (
        "🔄 AutoDB batch в работе\n"
        f"Run ID: {run_id}\n"
        f"{cycle_line}"
        f"Обработано: {progress_current}/{progress_total}\n"
        f"Связано: {int(linked)}\n"
        f"Ошибки: {int(errors)}\n"
        f"Квота: {int(quota_used)}/{max(int(quota_limit or 0), 0)}"
    )
    try:
        _send_telegram_message(token=token, chat_id=chat_id, text=text)
    except TelegramDispatchError as exc:
        logger.warning("Telegram system AutoDB batch progress notification failed: %s", exc)


def send_system_autodb_batch_stopped_notification(
    *,
    run_id: str,
    actor_name: str,
    processed: int,
    found: int,
    linked: int,
    not_found: int,
    stop_reason: str,
) -> None:
    channel = _get_system_channel_for_batch_notifications()
    if channel is None:
        return
    token, chat_id = channel
    text = (
        "AutoDB batch остановлен\n"
        f"Run ID: {run_id}\n"
        f"Сотрудник: {actor_name or '-'}\n"
        f"Обработано: {int(processed)}\n"
        f"Найдено: {int(found)}\n"
        f"Связано: {int(linked)}\n"
        f"Не найдено: {int(not_found)}\n"
        f"Причина: {_batch_stop_reason_label_ru(stop_reason)}"
    )
    try:
        _send_telegram_message(token=token, chat_id=chat_id, text=text)
    except TelegramDispatchError as exc:
        logger.warning("Telegram system AutoDB batch stopped notification failed: %s", exc)


def send_system_autodb_batch_finished_notification(
    *,
    run_id: str,
    final_status: str,
    batch_size: int,
    processed: int,
    linked: int,
    errors: int,
    quota_used: int,
    quota_limit: int,
    stop_reason: str,
    last_error: str,
) -> None:
    channel = _get_system_channel_for_batch_notifications()
    if channel is None:
        return
    token, chat_id = channel
    text = (
        "AutoDB batch завершен\n"
        f"Run ID: {run_id}\n"
        f"Статус: {final_status or '-'}\n"
        f"Обработано: {int(processed)}/{max(int(batch_size or 0), 0)}\n"
        f"Связано: {int(linked)}\n"
        f"Ошибки: {int(errors)}\n"
        f"Квота: {int(quota_used)}/{max(int(quota_limit or 0), 0)}"
    )
    if stop_reason:
        text += f"\nПричина остановки: {_batch_stop_reason_label_ru(stop_reason)}"
    if last_error and str(stop_reason or "").strip().lower() != "quota_or_remote_error":
        text += f"\nОшибка: {last_error}"
    try:
        _send_telegram_message(token=token, chat_id=chat_id, text=text)
    except TelegramDispatchError as exc:
        logger.warning("Telegram system AutoDB batch finished notification failed: %s", exc)


def send_system_autodb_quota_recovered_notification(*, remote_key: str = "known") -> None:
    channel = _get_system_channel_for_batch_notifications()
    if channel is None:
        return
    token, chat_id = channel
    text = (
        "AutoDB квота восстановлена\n"
        f"Источник: {remote_key or 'known'}\n"
        "Статус: удаленный поиск снова доступен"
    )
    try:
        _send_telegram_message(token=token, chat_id=chat_id, text=text)
    except TelegramDispatchError as exc:
        logger.warning("Telegram system AutoDB quota recovered notification failed: %s", exc)


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
