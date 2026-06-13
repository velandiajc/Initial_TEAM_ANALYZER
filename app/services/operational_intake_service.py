from collections import defaultdict
from pathlib import Path
from uuid import uuid4

import pandas as pd

from app.core.permissions import OperationalIntakePermission
from app.models.operational_intake import (
    OperationalIntakePriority,
    OperationalIntakeRecord,
    OperationalIntakeReport,
    OperationalIntakeRun,
)
from app.services.legacy_governance import LegacyGovernanceSupport
from app.services.pci_redaction_service import PCIRedactionService


PROJECTED_FIELDS = (
    "contact_id",
    "agent_id",
    "agent_name",
    "score",
    "survey_date",
    "brand",
    "media_type",
    "driver",
    "sub_driver",
    "csat_category",
    "disposition",
)

REQUIRED_COLUMN_GROUPS = (
    ("contactid",),
    ("OSAT",),
    ("agentname", "Agent Clean"),
    ("Driver_Tag",),
    ("Sub_Driver",),
    ("CSAT Category (Auto)",),
)


class OperationalIntakeService(LegacyGovernanceSupport):
    UNKNOWN_DRIVER = "Unspecified"

    def __init__(self, repository, audit_service, rbac_service=None):
        super().__init__(audit_service, rbac_service)
        self.repository = repository
        self.pci_redaction_service = PCIRedactionService()

    def run_from_file(self, context, file_path, reports_folder="Reports"):
        context = self.require_context(context)
        source_path = Path(file_path)
        reports_folder = Path(reports_folder)
        self.require_permission(
            context,
            OperationalIntakePermission.RUN_OPERATIONAL_INTAKE,
            "operational_intake_source",
            source_path.name,
        )
        self.audit(
            context,
            "OPERATIONAL_INTAKE_STARTED",
            "operational_intake_source",
            source_path.name,
        )

        dataframe, source_metadata = self._read_source(source_path)
        projected_rows = [
            self._project_allowed_fields(row, dataframe.columns)
            for row in dataframe.to_dict(orient="records")
        ]
        run_id = str(uuid4())
        records = [
            self._build_record(context, run_id, row)
            for row in projected_rows
            if row["contact_id"]
        ]
        priorities = self._build_priorities(context, run_id, records)
        run = OperationalIntakeRun(
            tenant_id=context.tenant_id,
            run_id=run_id,
            source_file=str(source_path),
            source_file_name=source_path.name,
            total_records=len(records),
            detractor_count=sum(
                1
                for record in records
                if record.classification == "Detractor"
            ),
            created_by=context.user_id,
            metadata={
                **source_metadata,
                "projected_fields": list(PROJECTED_FIELDS),
                "parity_expected_by_contact": {
                    row["contact_id"]: self._parity_expected(row)
                    for row in projected_rows
                    if row["contact_id"]
                },
            },
            records=records,
            priorities=priorities,
        )
        parity = self._build_parity(run)
        report = self._build_report(run, reports_folder, parity)
        reports_folder.mkdir(parents=True, exist_ok=True)
        Path(report.report_path).write_text(report.content, encoding="utf-8")
        self.repository.save_run(context, run, report)
        self.audit(
            context,
            "OPERATIONAL_INTAKE_COMPLETED",
            "operational_intake_run",
            run.run_id,
            {
                "total_records": run.total_records,
                "detractor_count": run.detractor_count,
                "priority_count": len(run.priorities),
            },
        )
        return run, report

    def _read_source(self, source_path):
        if not source_path.exists():
            raise FileNotFoundError(f"Intake file not found: {source_path}")

        suffix = source_path.suffix.lower()
        if suffix == ".csv":
            dataframe = pd.read_csv(source_path, encoding="utf-8-sig")
            self._validate_required_columns(dataframe, source_path.name)
            return dataframe, {
                "source_type": "csv",
                "selected_sheet": "",
            }

        if suffix in {".xlsx", ".xls"}:
            workbook = pd.ExcelFile(source_path)
            sheet_failures = {}
            for sheet_name in workbook.sheet_names:
                dataframe = pd.read_excel(workbook, sheet_name=sheet_name)
                missing = self._missing_required_columns(dataframe)
                if not missing:
                    return dataframe, {
                        "source_type": "excel",
                        "selected_sheet": sheet_name,
                    }
                sheet_failures[sheet_name] = missing

            details = "; ".join(
                f"{sheet}: missing {', '.join(missing)}"
                for sheet, missing in sheet_failures.items()
            )
            raise ValueError(
                "No valid CSAT intake sheet found. Required columns: "
                + self._required_columns_message()
                + f". Sheet results: {details}"
            )

        raise ValueError("Operational intake supports .csv, .xlsx, and .xls files.")

    def _project_allowed_fields(self, source_row, columns):
        return {
            "contact_id": self._source_value(source_row, columns, "contactid"),
            "agent_id": self._source_value(source_row, columns, "agentno", "ano"),
            "agent_name": self._source_value(
                source_row,
                columns,
                "agentname",
                "Agent Clean",
            ),
            "score": self._score(self._source_value(source_row, columns, "OSAT")),
            "survey_date": self._source_value(source_row, columns, "Date of Survey"),
            "brand": self._source_value(source_row, columns, "brand"),
            "media_type": self._source_value(source_row, columns, "media_type_name"),
            "driver": (
                self._source_value(source_row, columns, "Driver_Tag")
                or self.UNKNOWN_DRIVER
            ),
            "sub_driver": self._source_value(source_row, columns, "Sub_Driver"),
            "csat_category": self._source_value(
                source_row,
                columns,
                "CSAT Category (Auto)",
            ),
            "disposition": self._source_value(
                source_row,
                columns,
                "disposition_name",
            ),
        }

    def _build_record(self, context, run_id, row):
        classification = self._classify_score(row["score"])
        impact_score = self._record_impact_score(row["score"], classification)
        return OperationalIntakeRecord(
            tenant_id=context.tenant_id,
            run_id=run_id,
            contact_id=row["contact_id"],
            agent_id=row["agent_id"],
            agent_name=row["agent_name"],
            score=row["score"],
            classification=classification,
            driver=row["driver"],
            sub_driver=row["sub_driver"],
            csat_category=row["csat_category"],
            impact_score=impact_score,
            survey_date=row["survey_date"],
            brand=row["brand"],
            media_type=row["media_type"],
            disposition=row["disposition"],
        )

    def _build_priorities(self, context, run_id, records):
        grouped = defaultdict(list)
        for record in records:
            if record.classification == "Detractor":
                grouped[record.driver].append(record)

        priority_rows = []
        for driver, driver_records in grouped.items():
            detractor_count = len(driver_records)
            impact_score = round(
                sum(record.impact_score for record in driver_records),
                2,
            )
            priority_rows.append({
                "driver": driver,
                "detractor_count": detractor_count,
                "impact_score": impact_score,
            })

        impact_sorted = sorted(
            priority_rows,
            key=lambda row: (-row["impact_score"], row["driver"].lower()),
        )
        impact_ranks = {
            row["driver"]: index
            for index, row in enumerate(impact_sorted, start=1)
        }
        priority_sorted = sorted(
            priority_rows,
            key=lambda row: (
                -row["detractor_count"],
                -row["impact_score"],
                row["driver"].lower(),
            ),
        )

        return [
            OperationalIntakePriority(
                tenant_id=context.tenant_id,
                run_id=run_id,
                driver=row["driver"],
                detractor_count=row["detractor_count"],
                impact_score=row["impact_score"],
                impact_rank=impact_ranks[row["driver"]],
                priority_rank=index,
                priority_reason=(
                    f"{row['detractor_count']} detractor responses with "
                    f"{row['impact_score']} impact score."
                ),
            )
            for index, row in enumerate(priority_sorted, start=1)
        ]

    def _build_report(self, run, reports_folder, parity=None):
        parity = parity or self._build_parity(run)
        report_path = reports_folder / f"operational_intake_{run.run_id}.md"
        lines = [
            "# Operational Intake Parity Report",
            "",
            f"- Run ID: {run.run_id}",
            f"- Source File: {run.source_file_name}",
            f"- Total Records: {run.total_records}",
            f"- Detractor Count: {run.detractor_count}",
            f"- Selected Sheet: {run.metadata.get('selected_sheet', '')}",
            "",
            "## Priority Ranking",
        ]

        if not run.priorities:
            lines.append("- No detractor priorities found.")
        else:
            for priority in run.priorities:
                lines.append(
                    "- "
                    f"{priority.priority_rank}. {priority.driver} | "
                    f"Detractors: {priority.detractor_count} | "
                    f"Impact Score: {priority.impact_score} | "
                    f"Impact Rank: {priority.impact_rank}"
                )

        lines.extend([
            "",
            "## Allowed Projection",
            "- " + ", ".join(PROJECTED_FIELDS),
            "",
            "## Field-Level Parity",
            f"- Total Records: {parity['total_records']}",
            (
                "- Classification Match Count: "
                f"{parity['match_counts']['classification']}"
            ),
            f"- Driver Match Count: {parity['match_counts']['driver']}",
            f"- Sub-Driver Match Count: {parity['match_counts']['sub_driver']}",
            (
                "- CSAT Category Match Count: "
                f"{parity['match_counts']['csat_category']}"
            ),
            "",
            "## Parity Mismatches",
        ])

        if not parity["mismatches"]:
            lines.append("- None")
        else:
            for mismatch in parity["mismatches"]:
                lines.append(
                    "- "
                    f"{mismatch['contact_id']} | "
                    f"{mismatch['field_name']} | "
                    f"expected={mismatch['expected_value']} | "
                    f"actual={mismatch['actual_value']}"
                )

        lines.extend([
            "",
            "## Detractor Classification",
        ])

        for record in run.records:
            if record.classification != "Detractor":
                continue
            lines.append(
                "- "
                f"{record.contact_id} | {record.driver} | "
                f"Score: {record.score} | Impact Score: {record.impact_score}"
            )

        return OperationalIntakeReport(
            tenant_id=run.tenant_id,
            run_id=run.run_id,
            report_path=str(report_path),
            content="\n".join(lines) + "\n",
        )

    def _classify_score(self, score):
        if score >= 9:
            return "Promoter"
        if score >= 7:
            return "Neutral"
        return "Detractor"

    def _record_impact_score(self, score, classification):
        if classification != "Detractor":
            return 0.0
        return round(max(0.0, 10.0 - float(score)), 2)

    def _build_parity(self, run):
        expected_by_contact = run.metadata.get("parity_expected_by_contact", {})
        fields = ("classification", "driver", "sub_driver", "csat_category")
        match_counts = {
            field: 0
            for field in fields
        }
        mismatches = []

        for record in run.records:
            expected = expected_by_contact.get(record.contact_id, {})
            actual = {
                "classification": record.classification,
                "driver": record.driver,
                "sub_driver": record.sub_driver,
                "csat_category": record.csat_category,
            }
            for field in fields:
                expected_value = expected.get(field, "")
                actual_value = actual[field]
                if self._parity_value(field, expected_value) == self._parity_value(
                    field,
                    actual_value,
                ):
                    match_counts[field] += 1
                else:
                    mismatches.append({
                        "contact_id": record.contact_id,
                        "field_name": field,
                        "expected_value": self._clean(expected_value),
                        "actual_value": self._clean(actual_value),
                    })

        return {
            "total_records": len(run.records),
            "match_counts": match_counts,
            "mismatches": mismatches,
        }

    def _parity_expected(self, row):
        return {
            "classification": self._classify_score(row["score"]),
            "driver": row["driver"],
            "sub_driver": row["sub_driver"],
            "csat_category": row["csat_category"],
        }

    def _parity_value(self, field, value):
        if field == "classification":
            return self._normalize_classification(value)
        return self._clean(value).casefold()

    def _normalize_classification(self, value):
        normalized = self._clean(value).casefold()
        if normalized in {"dsat", "detractor", "detractors"}:
            return "detractor"
        if normalized in {"promoter", "promoters", "promotor"}:
            return "promoter"
        if normalized in {"neutral", "neutrals", "passive", "passives"}:
            return "neutral"
        return normalized

    def _source_value(self, source_row, columns, *column_names):
        column_lookup = self._source_columns(columns)
        for column_name in column_names:
            source_column = column_lookup.get(self._normalize_column_name(column_name))
            if source_column is None:
                continue
            value = self._clean(source_row.get(source_column))
            if value:
                return value
        return ""

    def _validate_required_columns(self, dataframe, source_name):
        missing = self._missing_required_columns(dataframe)
        if missing:
            raise ValueError(
                f"Invalid CSAT intake source {source_name}. Missing required "
                f"columns: {', '.join(missing)}. Required columns: "
                + self._required_columns_message()
            )

    def _missing_required_columns(self, dataframe):
        column_lookup = self._source_columns(dataframe.columns)
        missing = []
        for group in REQUIRED_COLUMN_GROUPS:
            if not any(
                self._normalize_column_name(column) in column_lookup
                for column in group
            ):
                missing.append(" or ".join(group))
        return missing

    def _required_columns_message(self):
        return ", ".join(
            " or ".join(group)
            for group in REQUIRED_COLUMN_GROUPS
        )

    def _source_columns(self, columns):
        return {
            self._normalize_column_name(column): column
            for column in columns
        }

    def _normalize_column_name(self, column_name):
        return " ".join(str(column_name).strip().lower().split())

    def _score(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _clean(self, value):
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except TypeError:
            pass
        text = str(value).strip()
        if text.lower() in {"nan", "none", "null"}:
            return ""
        return self.pci_redaction_service.redact(text)
