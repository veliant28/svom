from __future__ import annotations

import uuid
from datetime import datetime


def generate_order_number() -> str:
    now = datetime.now().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:8].upper()
    return f"ORD-{now}-{suffix}"
