from uuid import uuid4

from app.application.performance.services._service import (
    PerformanceServiceSupport,
)
from app.core.permissions import (
    CoachingPermission,
    GovernanceRole,
)
from app.domain.performance.entities import CoachingNote
from app.domain.performance.value_objects import (
    CoachingAuditEvent,
    CoachingNoteVisibility,
)


class CoachingNoteService(PerformanceServiceSupport):
    def __init__(
        self,
        note_repository,
        session_repository,
        audit_service,
        rbac_service=None,
    ):
        super().__init__(audit_service, rbac_service)
        self.note_repository = note_repository
        self.session_repository = session_repository

    def create_note(
        self,
        context,
        session_id,
        visibility_level,
        content_reference,
        note_id=None,
    ):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.EDIT_COACHING_SESSION,
            "coaching_note",
            note_id or "new",
        )
        session = self.require_entity(
            context,
            self.session_repository.get_session(context, session_id),
            "coaching_session",
            session_id,
        )
        note = CoachingNote(
            note_id=note_id or str(uuid4()),
            tenant_id=context.tenant_id,
            session_id=session_id,
            visibility_level=visibility_level,
            content_reference=content_reference,
            lineage_id=session.lineage_id,
            created_by=context.user_id,
            updated_by=context.user_id,
        )
        self.note_repository.save(context, note)
        self.audit(
            context,
            CoachingAuditEvent.NOTE_CREATED,
            "coaching_note",
            note.note_id,
            {
                "session_id": session_id,
                "visibility_level": note.visibility_level.value,
                "lineage_id": note.lineage_id,
            },
        )
        return note

    def get_note(self, context, note_id):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.VIEW_COACHING_SESSION,
            "coaching_note",
            note_id,
        )
        note = self.require_entity(
            context,
            self.note_repository.get_note(context, note_id),
            "coaching_note",
            note_id,
        )
        self._authorize_visibility(context, note)
        if note.visibility_level != CoachingNoteVisibility.SHARED:
            self.audit(
                context,
                CoachingAuditEvent.PRIVATE_NOTE_VIEWED,
                "coaching_note",
                note.note_id,
                {
                    "session_id": note.session_id,
                    "visibility_level": note.visibility_level.value,
                },
            )
        return note

    def list_visible_notes(self, context, session_id):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.VIEW_COACHING_SESSION,
            "coaching_session",
            session_id,
        )
        notes = self.note_repository.list_for_session(context, session_id)
        visible = []
        for note in notes:
            try:
                self._authorize_visibility(context, note)
            except PermissionError:
                continue
            visible.append(note)
        return visible

    def _authorize_visibility(self, context, note):
        if note.visibility_level == CoachingNoteVisibility.SHARED:
            return
        self.require_permission(
            context,
            CoachingPermission.VIEW_PRIVATE_COACHING_NOTE,
            "coaching_note",
            note.note_id,
        )
        privileged_roles = {
            GovernanceRole.GOVERNANCE_ADMIN.value,
            GovernanceRole.LEADERSHIP.value,
        }
        if note.visibility_level == CoachingNoteVisibility.MANAGER_ONLY:
            privileged_roles.add(
                GovernanceRole.PERFORMANCE_MANAGER.value
            )
        if not context.roles.intersection(privileged_roles):
            reason = (
                f"Role is not allowed to view "
                f"{note.visibility_level.value} coaching notes."
            )
            self.audit(
                context,
                CoachingAuditEvent.COACHING_ACCESS_DENIED,
                "coaching_note",
                note.note_id,
                {"reason": reason},
            )
            raise PermissionError(reason)
