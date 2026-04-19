from __future__ import annotations

NOVA_POSHTA_API_URL = "https://api.novaposhta.ua/v2.0/json/"
NOVA_POSHTA_PRINT_BASE_URL = "https://my.novaposhta.ua/orders"

WAYBILL_DESCRIPTION = "Автозапчасти и аксессуары"
WAYBILL_ADDITIONAL_INFO_TEMPLATE = "Номер заказа {order_number}"

FINAL_STATUS_CODES = {
    "2",  # удалено
    "9",  # получено
    "10",
    "11",
    "102",
    "103",
    "104",
    "105",
    "106",
}

DEFAULT_TIMEOUT_SECONDS = 20
LOOKUP_TIMEOUT_SECONDS = 12
