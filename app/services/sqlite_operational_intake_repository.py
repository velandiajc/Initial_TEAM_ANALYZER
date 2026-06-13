import json
from datetime import datetime

from app.core.permissions import OperationalIntakePermission
from app.models.operational_intake import (
    OperationalIntakePriority,
    OperationalIntakeRecord,
    OperationalIntakeReport,
    OperationalIntakeRun,
)
from app.services.legacy_governance import LegacyGovernanceSupport
from app.services.pci_redaction_service import PCIRedactionService


class SQLiteOperationalIntakeRepository(LegacyGovernanceSupport):
    def __init__(self, database_service, audit_service, rbac_service=None):
        super().__init__(audit_service, rbac_service)
        self.database_service = database_service
        self.pci_redaction_service = PCIRedactionService()

    def save_run(self, context, run, report):
        context = self.require_context(context)
        self.require_permission(
            context,
            OperationalIntakePermission.RUN_OPERATIONAL_INTAKE,
            "operational_intake_run",
            run.run_id,
        )
        if context.tenant_id != run.tenant_id or context.tenant_id != report.tenant_id:
            raise PermissionError("Operational intake write must be tenant-scoped.")

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO operational_intake_runs (
                    tenant_id,
                    run_id,
                    source_file,
                    source_file_name,
                    total_records,
                    detractor_count,
                    created_by,
                    created_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.tenant_id,
                run.run_id,
                self.pci_redaction_service.redact(run.source_file),
                self.pci_redaction_service.redact(run.source_file_name),
                run.total_records,
                run.detractor_count,
                run.created_by,
                run.created_at.isoformat(),
                json.dumps(run.metadata),
            ))

            for record in run.records:
                if record.tenant_id != run.tenant_id or record.run_id != run.run_id:
                    raise PermissionError(
                        "Operational intake record must match run tenant and id."
                    )
                cursor.execute("""
                    INSERT INTO operational_intake_records (
                        tenant_id,
                        intake_record_id,
                        run_id,
                        contact_id,
                        agent_id,
                        agent_name,
                        score,
                        classification,
                        driver,
                        sub_driver,
                        csat_category,
                        impact_score,
                        survey_date,
                        brand,
                        media_type,
                        disposition,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.tenant_id,
                    record.intake_record_id,
                    record.run_id,
                    self.pci_redaction_service.redact(record.contact_id),
                    self.pci_redaction_service.redact(record.agent_id),
                    self.pci_redaction_service.redact(record.agent_name),
                    record.score,
                    record.classification,
                    self.pci_redaction_service.redact(record.driver),
                    self.pci_redaction_service.redact(record.sub_driver),
                    self.pci_redaction_service.redact(record.csat_category),
                    record.impact_score,
                    self.pci_redaction_service.redact(record.survey_date),
                    self.pci_redaction_service.redact(record.brand),
                    self.pci_redaction_service.redact(record.media_type),
                    self.pci_redaction_service.redact(record.disposition),
                    record.created_at.isoformat(),
                ))

            for priority in run.priorities:
                if priority.tenant_id != run.tenant_id or priority.run_id != run.run_id:
                    raise PermissionError(
                        "Operational intake priority must match run tenant and id."
                    )
                cursor.execute("""
                    INSERT INTO operational_intake_priorities (
                        tenant_id,
                        priority_id,
                        run_id,
                        driver,
                        detractor_count,
                        impact_score,
                        impact_rank,
                        priority_rank,
                        priority_reason,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    priority.tenant_id,
                    priority.priority_id,
                    priority.run_id,
                    self.pci_redaction_service.redact(priority.driver),
                    priority.detractor_count,
                    priority.impact_score,
                    priority.impact_rank,
                    priority.priority_rank,
                    self.pci_redaction_service.redact(priority.priority_reason),
                    priority.created_at.isoformat(),
                ))

            if report.run_id != run.run_id:
                raise PermissionError("Operational intake report must match run id.")
            cursor.execute("""
                INSERT INTO operational_intake_reports (
                    tenant_id,
                    report_id,
                    run_id,
                    report_path,
                    content,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                report.tenant_id,
                report.report_id,
                report.run_id,
                self.pci_redaction_service.redact(report.report_path),
                self.pci_redaction_service.redact(report.content),
                report.created_at.isoformat(),
            ))
            conn.commit()

        self.audit(
            context,
            "OPERATIONAL_INTAKE_RUN_PERSISTED",
            "operational_intake_run",
            run.run_id,
            {
                "total_records": run.total_records,
                "detractor_count": run.detractor_count,
                "priority_count": len(run.priorities),
            },
        )
        self.audit(
            context,
            "OPERATIONAL_INTAKE_PARITY_REPORT_PERSISTED",
            "operational_intake_report",
            report.report_id,
            {
                "run_id": run.run_id,
                "report_path": report.report_path,
            },
        )

    def get_run(self, context, run_id):
        context = self.require_context(context)
        self.require_permission(
            context,
            OperationalIntakePermission.VIEW_OPERATIONAL_INTAKE,
            "operational_intake_run",
            run_id,
        )
        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    run_id,
                    source_file,
                    source_file_name,
                    total_records,
                    detractor_count,
                    created_by,
                    created_at,
                    metadata_json
                FROM operational_intake_runs
                WHERE tenant_id = ? AND run_id = ?
            """, (context.tenant_id, run_id))
            row = cursor.fetchone()

        if row is None:
            return None

        return OperationalIntakeRun(
            tenant_id=row[0],
            run_id=row[1],
            source_file=row[2],
            source_file_name=row[3],
            total_records=row[4],
            detractor_count=row[5],
            created_by=row[6],
            created_at=datetime.fromisoformat(row[7]),
            metadata=json.loads(row[8] or "{}"),
        )

    def list_records(self, context, run_id):
        context = self.require_context(context)
        self.require_permission(
            context,
            OperationalIntakePermission.VIEW_OPERATIONAL_INTAKE,
            "operational_intake_run",
            run_id,
        )
        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    intake_record_id,
                    run_id,
                    contact_id,
                    agent_id,
                    agent_name,
                    score,
                    classification,
                    driver,
                    sub_driver,
                    csat_category,
                    impact_score,
                    survey_date,
                    brand,
                    media_type,
                    disposition,
                    created_at
                FROM operational_intake_records
                WHERE tenant_id = ? AND run_id = ?
                ORDER BY contact_id
            """, (context.tenant_id, run_id))
            rows = cursor.fetchall()

        return [
            OperationalIntakeRecord(
                tenant_id=row[0],
                intake_record_id=row[1],
                run_id=row[2],
                contact_id=row[3],
                agent_id=row[4],
                agent_name=row[5],
                score=row[6],
                classification=row[7],
                driver=row[8],
                sub_driver=row[9],
                csat_category=row[10],
                impact_score=row[11],
                survey_date=row[12],
                brand=row[13],
                media_type=row[14],
                disposition=row[15],
                created_at=datetime.fromisoformat(row[16]),
            )
            for row in rows
        ]

    def list_priorities(self, context, run_id):
        context = self.require_context(context)
        self.require_permission(
            context,
            OperationalIntakePermission.VIEW_OPERATIONAL_INTAKE,
            "operational_intake_run",
            run_id,
        )
        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    priority_id,
                    run_id,
                    driver,
                    detractor_count,
                    impact_score,
                    impact_rank,
                    priority_rank,
                    priority_reason,
                    created_at
                FROM operational_intake_priorities
                WHERE tenant_id = ? AND run_id = ?
                ORDER BY priority_rank
            """, (context.tenant_id, run_id))
            rows = cursor.fetchall()

        return [
            OperationalIntakePriority(
                tenant_id=row[0],
                priority_id=row[1],
                run_id=row[2],
                driver=row[3],
                detractor_count=row[4],
                impact_score=row[5],
                impact_rank=row[6],
                priority_rank=row[7],
                priority_reason=row[8],
                created_at=datetime.fromisoformat(row[9]),
            )
            for row in rows
        ]

    def get_report(self, context, run_id):
        context = self.require_context(context)
        self.require_permission(
            context,
            OperationalIntakePermission.VIEW_OPERATIONAL_INTAKE,
            "operational_intake_run",
            run_id,
        )
        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    report_id,
                    run_id,
                    report_path,
                    content,
                    created_at
                FROM operational_intake_reports
                WHERE tenant_id = ? AND run_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (context.tenant_id, run_id))
            row = cursor.fetchone()

        if row is None:
            return None

        return OperationalIntakeReport(
            tenant_id=row[0],
            report_id=row[1],
            run_id=row[2],
            report_path=row[3],
            content=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )
