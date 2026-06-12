from app.application.workspace.services import (
    SupervisorCoachingWorkspaceService,
    SupervisorPriorityQueueService,
    SupervisorProfileService,
    SupervisorTimelineService,
    SupervisorWorkspaceService,
)
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository


def build_workspace_stack(tmp_path):
    database = DatabaseService(tmp_path / "workspace-integration.db")
    database.initialize()
    audit_repository = SQLiteKPIAuditRepository(database)
    audit_service = KPIAuditService(audit_repository)
    priority_queue = SupervisorPriorityQueueService(audit_service)
    profile = SupervisorProfileService(audit_service)
    timeline = SupervisorTimelineService(audit_service)
    coaching = SupervisorCoachingWorkspaceService(audit_service)
    workspace = SupervisorWorkspaceService(
        audit_service,
        priority_queue,
        profile,
        timeline,
        coaching,
    )
    return {
        "database": database,
        "audit_repository": audit_repository,
        "audit_service": audit_service,
        "priority_queue": priority_queue,
        "profile": profile,
        "timeline": timeline,
        "coaching": coaching,
        "workspace": workspace,
    }
