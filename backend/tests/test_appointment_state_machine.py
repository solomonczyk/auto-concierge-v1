import pytest
from app.models.models import AppointmentStatus as S, UserRole
from app.services.appointment_state_machine import (
    validate_transition,
    TransitionError,
    ALLOWED_TRANSITIONS,
)


class TestAllowedTransitions:
    def test_new_to_confirmed(self):
        validate_transition(current=S.NEW, target=S.CONFIRMED, role=UserRole.ADMIN)

    def test_new_to_cancelled(self):
        validate_transition(current=S.NEW, target=S.CANCELLED, role=UserRole.ADMIN)

    def test_confirmed_to_in_progress(self):
        validate_transition(current=S.CONFIRMED, target=S.IN_PROGRESS, role=UserRole.STAFF)

    def test_in_progress_to_completed(self):
        validate_transition(current=S.IN_PROGRESS, target=S.COMPLETED, role=UserRole.STAFF)

    def test_same_status_rejected(self):
        with pytest.raises(TransitionError) as exc:
            validate_transition(current=S.COMPLETED, target=S.COMPLETED, role=UserRole.ADMIN)
        assert exc.value.code == "same_status"

    def test_confirmed_to_no_show(self):
        validate_transition(current=S.CONFIRMED, target=S.NO_SHOW, role=UserRole.ADMIN)

    def test_waitlist_to_new(self):
        validate_transition(current=S.WAITLIST, target=S.NEW, role=UserRole.ADMIN)


class TestForbiddenTransitions:
    def test_completed_to_new(self):
        with pytest.raises(TransitionError) as exc:
            validate_transition(current=S.COMPLETED, target=S.NEW, role=UserRole.ADMIN)
        assert exc.value.code == "invalid_transition"

    def test_cancelled_to_confirmed(self):
        with pytest.raises(TransitionError) as exc:
            validate_transition(current=S.CANCELLED, target=S.CONFIRMED, role=UserRole.ADMIN)
        assert exc.value.code == "invalid_transition"

    def test_no_show_to_in_progress(self):
        with pytest.raises(TransitionError) as exc:
            validate_transition(current=S.NO_SHOW, target=S.IN_PROGRESS, role=UserRole.ADMIN)
        assert exc.value.code == "invalid_transition"

    def test_completed_to_in_progress(self):
        with pytest.raises(TransitionError) as exc:
            validate_transition(current=S.COMPLETED, target=S.IN_PROGRESS, role=UserRole.ADMIN)
        assert exc.value.code == "invalid_transition"


class TestRolePermissions:
    def test_staff_cannot_confirm(self):
        with pytest.raises(TransitionError) as exc:
            validate_transition(current=S.NEW, target=S.CONFIRMED, role=UserRole.STAFF)
        assert exc.value.code == "permission_denied"

    def test_staff_can_start(self):
        validate_transition(current=S.CONFIRMED, target=S.IN_PROGRESS, role=UserRole.STAFF)

    def test_staff_can_complete(self):
        validate_transition(current=S.IN_PROGRESS, target=S.COMPLETED, role=UserRole.STAFF)

    def test_manager_can_confirm(self):
        validate_transition(current=S.NEW, target=S.CONFIRMED, role=UserRole.MANAGER)

    def test_manager_can_cancel(self):
        validate_transition(current=S.NEW, target=S.CANCELLED, role=UserRole.MANAGER)

    def test_manager_cannot_start(self):
        with pytest.raises(TransitionError) as exc:
            validate_transition(current=S.CONFIRMED, target=S.IN_PROGRESS, role=UserRole.MANAGER)
        assert exc.value.code == "permission_denied"

    def test_admin_can_do_anything_allowed(self):
        for current, targets in ALLOWED_TRANSITIONS.items():
            for target in targets:
                validate_transition(current=current, target=target, role=UserRole.ADMIN)


class TestSystemTransitions:
    def test_system_can_no_show(self):
        validate_transition(current=S.CONFIRMED, target=S.NO_SHOW, is_system=True)

    def test_system_can_cancel(self):
        validate_transition(current=S.NEW, target=S.CANCELLED, is_system=True)

    def test_system_cannot_confirm(self):
        with pytest.raises(TransitionError) as exc:
            validate_transition(current=S.NEW, target=S.CONFIRMED, is_system=True)
        assert exc.value.code == "permission_denied"
