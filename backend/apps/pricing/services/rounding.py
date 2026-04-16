from decimal import Decimal, ROUND_HALF_UP, ROUND_UP

MONEY_QUANT = Decimal("0.01")


def to_decimal(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_money(value: Decimal | int | float | str | None) -> Decimal:
    return to_decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def apply_step_rounding(value: Decimal, step: Decimal | int | float | str | None) -> Decimal:
    step_decimal = to_decimal(step)
    if step_decimal <= 0:
        return quantize_money(value)

    rounded = (to_decimal(value) / step_decimal).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step_decimal
    return quantize_money(rounded)


def apply_psychological_rounding(value: Decimal) -> Decimal:
    amount = quantize_money(value)
    if amount <= Decimal("1"):
        return amount

    rounded_up_integer = amount.quantize(Decimal("1"), rounding=ROUND_UP)
    psychological = rounded_up_integer - Decimal("0.01")
    return quantize_money(psychological)
