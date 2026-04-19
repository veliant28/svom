from __future__ import annotations

from . import status


def serialize_supplier_row(*, source, integration, cooldown) -> dict:
    return {
        "code": source.code,
        "name": source.name,
        "supplier_name": source.supplier.name,
        "is_enabled": integration.is_enabled,
        "connection_status": status.resolve_connection_status(integration=integration),
        "last_successful_import_at": integration.last_successful_import_at or source.last_success_at,
        "last_failed_import_at": integration.last_failed_import_at or source.last_failed_at,
        "can_run_now": cooldown.can_run,
        "cooldown_wait_seconds": cooldown.wait_seconds,
    }


def serialize_workspace_payload(*, source, integration, latest_run, latest_error, cooldown) -> dict:
    return {
        "supplier": {
            "code": source.code,
            "name": source.name,
            "supplier_name": source.supplier.name,
            "is_enabled": integration.is_enabled,
        },
        "connection": {
            "login": integration.login,
            "has_password": bool(integration.password),
            "access_token_masked": integration.masked_access_token,
            "refresh_token_masked": integration.masked_refresh_token,
            "access_token_expires_at": integration.access_token_expires_at,
            "refresh_token_expires_at": integration.refresh_token_expires_at,
            "token_obtained_at": integration.token_obtained_at,
            "last_token_refresh_at": integration.last_token_refresh_at,
            "last_token_error_at": integration.last_token_error_at,
            "last_token_error_message": integration.last_token_error_message,
            "credentials_updated_at": integration.credentials_updated_at,
            "status": status.resolve_connection_status(integration=integration),
            "last_connection_check_at": integration.last_connection_check_at,
            "last_connection_status": integration.last_connection_status,
        },
        "import": {
            "last_run_status": latest_run.status if latest_run else "",
            "last_run_at": latest_run.created_at if latest_run else None,
            "last_successful_import_at": integration.last_successful_import_at or source.last_success_at,
            "last_failed_import_at": integration.last_failed_import_at or source.last_failed_at,
            "last_import_error_message": integration.last_import_error_message or (latest_error.message if latest_error else ""),
            "last_run_summary": latest_run.summary if latest_run else {},
            "last_run_processed_rows": latest_run.processed_rows if latest_run else 0,
            "last_run_errors_count": latest_run.errors_count if latest_run else 0,
        },
        "cooldown": {
            "last_request_at": cooldown.last_request_at,
            "next_allowed_request_at": cooldown.next_allowed_request_at,
            "can_run": cooldown.can_run,
            "wait_seconds": cooldown.wait_seconds,
            "cooldown_seconds": cooldown.cooldown_seconds,
            "status_label": status.cooldown_status_label(can_run=cooldown.can_run, wait_seconds=cooldown.wait_seconds),
        },
        "utr": {
            "available": source.code == "utr",
            "last_brands_import_at": integration.last_brands_import_at,
            "last_brands_import_count": integration.last_brands_import_count,
            "last_brands_import_error_at": integration.last_brands_import_error_at,
            "last_brands_import_error_message": integration.last_brands_import_error_message,
        },
    }


def serialize_cooldown_payload(*, supplier_code: str, cooldown) -> dict:
    return {
        "supplier_code": supplier_code,
        "last_request_at": cooldown.last_request_at,
        "next_allowed_request_at": cooldown.next_allowed_request_at,
        "can_run": cooldown.can_run,
        "wait_seconds": cooldown.wait_seconds,
        "cooldown_seconds": cooldown.cooldown_seconds,
        "status_label": status.cooldown_status_label(can_run=cooldown.can_run, wait_seconds=cooldown.wait_seconds),
    }


def serialize_connection_check(*, details: dict, workspace_payload: dict) -> dict:
    return {
        "ok": True,
        "details": details,
        "workspace": workspace_payload,
    }


def serialize_orchestration_result(*, result) -> dict:
    return {"mode": result.mode, **result.payload}


def serialize_publish_mapped_result(*, result) -> dict:
    return {
        "mode": "sync",
        "result": result.as_dict(),
    }


def serialize_utr_brands_import_result(*, imported_count: int, source: str, summary, workspace_payload: dict) -> dict:
    return {
        "imported_count": imported_count,
        "source": source,
        "summary": summary.as_dict(),
        "workspace": workspace_payload,
    }
