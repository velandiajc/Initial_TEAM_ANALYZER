# Security Validation

Every pull request is subject to the repository's Security Validation workflow.

The workflow runs:

- the complete pytest suite;
- Bandit static analysis against `app` and `Scripts`;
- `pip-audit` against pinned direct dependencies; and
- Gitleaks secret scanning with full repository history available.

The workflow uses read-only repository permissions. A failing test or scan is
a merge blocker and must be reviewed by Engineering and Security. Suppressions
must be narrow, documented, and approved; broad scan exclusions are prohibited.
Bandit runs on Python 3.12, the supported CI scanner runtime.

SQLite persistence also creates database-level PCI insert and update guards
for every text column and append-only update/delete guards for KPI audit
events.

Local validation commands:

```powershell
python -m pytest -q
bandit -r app Scripts -x tests -ll
pip-audit -r Requirements.txt
```
