import { RoleGroupBadge } from "@/features/backoffice/components/rbac/role-group-badge";
import type { BackofficeStaffActor } from "@/features/backoffice/types/orders.types";

export function OrderModalStaffActor({
  actor,
}: {
  actor: BackofficeStaffActor | null;
}) {
  if (!actor) {
    return null;
  }

  const groupName = actor.role_group_name || "";

  return (
    <div className="min-w-[220px] max-w-[320px] text-right">
      {groupName ? (
        <RoleGroupBadge groupName={groupName} className="ml-auto" />
      ) : null}
      <p className="mt-1 text-xs leading-4" style={{ color: "var(--muted)" }}>
        {actor.full_name}
      </p>
    </div>
  );
}
