from __future__ import annotations

from collections.abc import Iterable

from rest_framework.permissions import BasePermission

from apps.backoffice.permissions.capability_rules import resolve_required_capabilities_for_request
from apps.users.rbac import user_has_capability


class IsStaffOrSuperuser(BasePermission):
    message = "Backoffice access is restricted."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not bool(user and user.is_authenticated):
            return False

        required = self._resolve_required_capabilities(request=request, view=view)
        missing = [code for code in required if not user_has_capability(user, code)]
        if missing:
            self.message = f"Missing backoffice capability: {', '.join(missing)}"
            return False
        return True

    def _resolve_required_capabilities(self, *, request, view) -> tuple[str, ...]:
        explicit_many = getattr(view, "required_capabilities", None)
        if isinstance(explicit_many, Iterable) and not isinstance(explicit_many, (str, bytes)):
            codes = [str(value or "").strip() for value in explicit_many if str(value or "").strip()]
            if codes:
                return tuple(codes)

        explicit_one = str(getattr(view, "required_capability", "") or "").strip()
        if explicit_one:
            return (explicit_one,)

        return resolve_required_capabilities_for_request(request.path, request.method)
