from dataclasses import dataclass, field
from datetime import datetime


def _text(value, field_name):
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    return text


@dataclass(frozen=True)
class WorkspaceFilters:
    team_id: str | None = None
    employee_id: str | None = None
    employee_ids: tuple[str, ...] = ()
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None

    def __post_init__(self):
        if (
            self.date_range_start
            and self.date_range_end
            and self.date_range_start > self.date_range_end
        ):
            raise ValueError(
                "date_range_start must be before or equal to date_range_end."
            )
        object.__setattr__(
            self,
            "employee_ids",
            tuple(
                dict.fromkeys(
                    _text(value, "employee_id")
                    for value in self.employee_ids
                )
            ),
        )


@dataclass(frozen=True)
class WorkspaceRequest:
    tenant_id: str
    requester_id: str
    supervisor_id: str
    filters: WorkspaceFilters = field(default_factory=WorkspaceFilters)

    def __post_init__(self):
        for name in ("tenant_id", "requester_id", "supervisor_id"):
            _text(getattr(self, name), name)


@dataclass(frozen=True)
class TeamWorkspaceRequest(WorkspaceRequest):
    team_id: str = ""
    employee_ids: tuple[str, ...] = ()

    def __post_init__(self):
        super().__post_init__()
        _text(self.team_id, "team_id")
        object.__setattr__(
            self,
            "employee_ids",
            tuple(
                dict.fromkeys(
                    _text(value, "employee_id")
                    for value in self.employee_ids
                )
            ),
        )


@dataclass(frozen=True)
class EmployeeWorkspaceRequest(WorkspaceRequest):
    employee_id: str = ""

    def __post_init__(self):
        super().__post_init__()
        _text(self.employee_id, "employee_id")
