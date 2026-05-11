from __future__ import annotations

from dataclasses import dataclass


PUBLIC_DETAIL_STATUS_ACTIVE = 200
PUBLIC_DETAIL_STATUS_INACTIVE = 404


@dataclass(frozen=True)
class LinkSmokeEvaluation:
    expected_public_detail_status: int
    public_detail_status: int
    status_matches_expectation: bool
    trusted_link_visible: bool
    attributes_unchanged: bool
    fitments_unchanged: bool
    images_unchanged: bool
    price_unchanged: bool
    stock_unchanged: bool
    smoke_ok: bool


def expected_public_detail_status(*, is_active: bool) -> int:
    return PUBLIC_DETAIL_STATUS_ACTIVE if bool(is_active) else PUBLIC_DETAIL_STATUS_INACTIVE


def evaluate_link_smoke(
    *,
    is_active: bool,
    public_detail_status: int,
    trusted_link_visible: bool,
    attributes_unchanged: bool,
    fitments_unchanged: bool,
    images_unchanged: bool,
    price_unchanged: bool,
    stock_unchanged: bool,
) -> LinkSmokeEvaluation:
    expected_status = expected_public_detail_status(is_active=is_active)
    status_ok = int(public_detail_status or 0) == expected_status
    invariants_ok = all(
        [
            bool(trusted_link_visible),
            bool(attributes_unchanged),
            bool(fitments_unchanged),
            bool(images_unchanged),
            bool(price_unchanged),
            bool(stock_unchanged),
        ]
    )

    return LinkSmokeEvaluation(
        expected_public_detail_status=expected_status,
        public_detail_status=int(public_detail_status or 0),
        status_matches_expectation=status_ok,
        trusted_link_visible=bool(trusted_link_visible),
        attributes_unchanged=bool(attributes_unchanged),
        fitments_unchanged=bool(fitments_unchanged),
        images_unchanged=bool(images_unchanged),
        price_unchanged=bool(price_unchanged),
        stock_unchanged=bool(stock_unchanged),
        smoke_ok=bool(status_ok and invariants_ok),
    )
