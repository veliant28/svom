from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from typing import Final


class MonobankSignatureError(RuntimeError):
    pass


OPENSSL_BIN: Final[str] = "openssl"


def sign_payload(*, payload: bytes, private_key: str) -> str:
    private_key_pem = _normalize_private_key(private_key)

    payload_path = ""
    private_key_path = ""
    signature_path = ""

    try:
        payload_path = _write_temp_bytes(payload)
        private_key_path = _write_temp_bytes(private_key_pem.encode("utf-8"))
        signature_path = _create_temp_path()

        result = subprocess.run(
            [OPENSSL_BIN, "dgst", "-sha256", "-sign", private_key_path, "-out", signature_path, payload_path],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise MonobankSignatureError(result.stderr.strip() or "Failed to sign Monobank payload.")

        with open(signature_path, "rb") as file_obj:
            signature_bytes = file_obj.read()
        return base64.b64encode(signature_bytes).decode("ascii")
    except OSError as exc:
        raise MonobankSignatureError("OpenSSL is unavailable for Monobank signature operations.") from exc
    finally:
        _safe_unlink(payload_path)
        _safe_unlink(private_key_path)
        _safe_unlink(signature_path)


def verify_signature(*, payload: bytes, signature_base64: str, public_key: str) -> bool:
    normalized_signature = (signature_base64 or "").strip()
    if not normalized_signature:
        return False

    public_key_pem = _normalize_public_key(public_key)

    payload_path = ""
    public_key_path = ""
    signature_path = ""

    try:
        signature_bytes = base64.b64decode(normalized_signature)
        payload_path = _write_temp_bytes(payload)
        public_key_path = _write_temp_bytes(public_key_pem.encode("utf-8"))
        signature_path = _write_temp_bytes(signature_bytes)

        result = subprocess.run(
            [OPENSSL_BIN, "dgst", "-sha256", "-verify", public_key_path, "-signature", signature_path, payload_path],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except (ValueError, OSError):
        return False
    finally:
        _safe_unlink(payload_path)
        _safe_unlink(public_key_path)
        _safe_unlink(signature_path)


def _normalize_private_key(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise MonobankSignatureError("Monobank private key is empty.")

    if normalized.startswith("-----BEGIN"):
        return normalized

    try:
        decoded = base64.b64decode(normalized).decode("utf-8")
        if decoded.strip().startswith("-----BEGIN"):
            return decoded.strip()
    except Exception:
        pass

    raise MonobankSignatureError("Monobank private key format is invalid.")


def _normalize_public_key(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise MonobankSignatureError("Monobank public key is empty.")

    if normalized.startswith("-----BEGIN"):
        return normalized

    try:
        decoded = base64.b64decode(normalized).decode("utf-8")
        if decoded.strip().startswith("-----BEGIN"):
            return decoded.strip()
    except Exception:
        pass

    raise MonobankSignatureError("Monobank public key format is invalid.")


def _create_temp_path() -> str:
    fd, path = tempfile.mkstemp(prefix="svom_mono_sig_")
    os.close(fd)
    return path


def _write_temp_bytes(data: bytes) -> str:
    fd, path = tempfile.mkstemp(prefix="svom_mono_sig_")
    os.close(fd)
    with open(path, "wb") as file_obj:
        file_obj.write(data)
    return path


def _safe_unlink(path: str) -> None:
    if not path:
        return
    try:
        os.unlink(path)
    except OSError:
        return
