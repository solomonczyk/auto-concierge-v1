"""Appointment lifecycle state machine.

Defines allowed status transitions and role-based guards.
Keeps business rules in one place instead of scattering across endpoints.
"""

from app.models.models import AppointmentStatus as S, UserRole

ALLOWED_TRANSITIONS: dict[S, set[S]] = {
    S.NEW:         {S.CONFIRMED, S.CANCELLED},
    S.CONFIRMED:   {S.IN_PROGRESS, S.CANCELLED, S.NO_SHOW},
    S.IN_PROGRESS: {S.COMPLETED, S.CANCELLED},
    S.COMPLETED:   set(),
    S.CANCELLED:   set(),
    S.NO_SHOW:     set(),
    S.WAITLIST:    {S.NEW, S.CANCELLED},
}

ROLE_PERMISSIONS: dict[UserRole, set[S]] = {
    UserRole.SUPERADMIN: {s for s in S},
    UserRole.ADMIN:      {s for s in S},
    UserRole.MANAGER:    {S.CONFIRMED, S.CANCELLED, S.NO_SHOW},
    UserRole.STAFF:      {S.IN_PROGRESS, S.COMPLETED},
}

SYSTEM_ALLOWED_TARGETS: set[S] = {S.NO_SHOW, S.CANCELLED}


class TransitionError(Exception):
    def __init__(self, message: str, code: str = "invalid_transition"):
        self.message = message
        self.code = code


def validate_transition(
    *,
    current: S,
    target: S,
    role: UserRole | None = None,
    is_system: bool = False,
) -> None:
    """Validate that the transition is allowed.

    Raises TransitionError if the transition is invalid or unauthorized.
    """
    if current == target:
        raise TransitionError(
            f"Already in status '{current.value}'",
            code="same_status",
        )

    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise TransitionError(
            f"Transition '{current.value}' → '{target.value}' is not allowed",
            code="invalid_transition",
        )

    if is_system:
        if target not in SYSTEM_ALLOWED_TARGETS:
            raise TransitionError(
                f"System cannot set status '{target.value}'",
                code="permission_denied",
            )
        return

    if role is None:
        raise TransitionError("Role is required", code="permission_denied")

    permitted = ROLE_PERMISSIONS.get(role, set())
    if target not in permitted:
        raise TransitionError(
            f"Role '{role.value}' cannot set status '{target.value}'",
            code="permission_denied",
        )
