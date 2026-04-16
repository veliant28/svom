from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from apps.catalog.models import Category, Product
from apps.pricing.models import PricingPolicy
from apps.pricing.tasks import recalculate_category_prices_task, recalculate_product_prices_task
from apps.backoffice.selectors.pricing_control_selectors import resolve_category_scope_ids


@dataclass(frozen=True)
class PricingApplyResult:
    mode: str
    affected_products: int
    target_categories: int = 0
    created_policies: int = 0
    updated_policies: int = 0
    markup_percent: str = "0.00"


class PricingControlService:
    @staticmethod
    def normalize_percent_markup(value: object) -> Decimal:
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0.00")

        if parsed < Decimal("0"):
            return Decimal("0.00")
        if parsed > Decimal("100"):
            return Decimal("100.00")
        return parsed.quantize(Decimal("0.01"))

    def apply_global_markup(
        self,
        *,
        percent_markup: Decimal,
        dispatch_async: bool,
    ) -> PricingApplyResult:
        policy = (
            PricingPolicy.objects.filter(scope=PricingPolicy.SCOPE_GLOBAL)
            .order_by("priority", "id")
            .first()
        )
        created = 0
        updated = 0
        if policy is None:
            policy = PricingPolicy.objects.create(
                name="Общая наценка",
                scope=PricingPolicy.SCOPE_GLOBAL,
                priority=100,
                percent_markup=percent_markup,
                is_active=True,
            )
            created = 1
        else:
            changed = False
            if policy.percent_markup != percent_markup:
                policy.percent_markup = percent_markup
                changed = True
            if not policy.is_active:
                policy.is_active = True
                changed = True
            if changed:
                policy.save(update_fields=("percent_markup", "is_active", "updated_at"))
                updated = 1

        affected_products = Product.objects.filter(is_active=True).count()
        mode = self._recalculate_all(dispatch_async=dispatch_async)
        return PricingApplyResult(
            mode=mode,
            affected_products=affected_products,
            created_policies=created,
            updated_policies=updated,
            markup_percent=str(percent_markup),
        )

    def apply_category_markup(
        self,
        *,
        category_id: str,
        percent_markup: Decimal,
        include_children: bool,
        dispatch_async: bool,
    ) -> PricingApplyResult:
        category_ids = resolve_category_scope_ids(category_id=category_id, include_children=include_children)
        categories = {str(item.id): item for item in Category.objects.filter(id__in=category_ids)}

        created = 0
        updated = 0
        for item_id in category_ids:
            category = categories.get(item_id)
            if category is None:
                continue

            policy = (
                PricingPolicy.objects.filter(scope=PricingPolicy.SCOPE_CATEGORY, category=category)
                .order_by("priority", "id")
                .first()
            )
            if policy is None:
                PricingPolicy.objects.create(
                    name=f"Наценка по категориям: {category.name} ({category.id})"[:180],
                    scope=PricingPolicy.SCOPE_CATEGORY,
                    category=category,
                    priority=60,
                    percent_markup=percent_markup,
                    is_active=True,
                )
                created += 1
                continue

            changed = False
            if policy.percent_markup != percent_markup:
                policy.percent_markup = percent_markup
                changed = True
            if not policy.is_active:
                policy.is_active = True
                changed = True
            if changed:
                policy.save(update_fields=("percent_markup", "is_active", "updated_at"))
                updated += 1

        affected_products = Product.objects.filter(is_active=True, category_id__in=category_ids).count()
        mode = self._recalculate_categories(category_ids=category_ids, dispatch_async=dispatch_async)
        return PricingApplyResult(
            mode=mode,
            affected_products=affected_products,
            target_categories=len(category_ids),
            created_policies=created,
            updated_policies=updated,
            markup_percent=str(percent_markup),
        )

    def recalculate(
        self,
        *,
        dispatch_async: bool,
        category_id: str | None = None,
        include_children: bool = False,
    ) -> PricingApplyResult:
        if category_id:
            category_ids = resolve_category_scope_ids(category_id=category_id, include_children=include_children)
            affected_products = Product.objects.filter(is_active=True, category_id__in=category_ids).count()
            mode = self._recalculate_categories(category_ids=category_ids, dispatch_async=dispatch_async)
            return PricingApplyResult(
                mode=mode,
                affected_products=affected_products,
                target_categories=len(category_ids),
            )

        affected_products = Product.objects.filter(is_active=True).count()
        mode = self._recalculate_all(dispatch_async=dispatch_async)
        return PricingApplyResult(mode=mode, affected_products=affected_products)

    @staticmethod
    def _recalculate_all(*, dispatch_async: bool) -> str:
        if dispatch_async:
            recalculate_product_prices_task.delay(
                product_ids=None,
                trigger_note="backoffice:pricing_panel_global",
            )
            return "async"
        recalculate_product_prices_task(
            product_ids=None,
            trigger_note="backoffice:pricing_panel_global_sync",
        )
        return "sync"

    @staticmethod
    def _recalculate_categories(*, category_ids: list[str], dispatch_async: bool) -> str:
        if dispatch_async:
            recalculate_category_prices_task.delay(
                category_ids=category_ids,
                trigger_note="backoffice:pricing_panel_category",
            )
            return "async"
        recalculate_category_prices_task(
            category_ids=category_ids,
            trigger_note="backoffice:pricing_panel_category_sync",
        )
        return "sync"
