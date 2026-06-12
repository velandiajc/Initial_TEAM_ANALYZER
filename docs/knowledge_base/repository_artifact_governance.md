# Repository Artifact Governance

## Purpose

This policy prevents operational data, generated analysis, local machine
inventories, and sensitive runtime artifacts from entering TEAM_ANALYZER source
control.

The repository is a product asset. It must contain source code, tests,
configuration, documentation, and approved structure-only templates only.

## Prohibited Artifacts

The following must never be committed:

- SQLite databases or database backups.
- Customer or employee data exports.
- Call recordings or other audio/video files.
- Raw or generated transcripts.
- Generated QA, coaching, survey, or risk analysis outputs.
- Reports containing operational records or customer comments.
- Repository tree dumps and machine inventories.
- Local workbook or dataset inventories.
- Runtime cache, temporary, or tool workspace files.
- Secrets, credentials, tokens, or environment files containing values.

## Required Storage Boundaries

Runtime inputs remain under `Data/`.

Generated outputs remain under `Reports/` or approved ignored runtime
directories.

Structure-only examples belong under `templates/` and must contain no real
identifiers, names, comments, recordings, or operational values.

Documentation under `docs/` may describe schemas and controls but must not copy
real operational payloads.

## Preventive Controls

`.gitignore` blocks databases, recordings, runtime data, reports, transcripts,
generated analyses, repository tree dumps, and local inventories.

CI secret scanning provides an additional gate. Ignore rules are not a security
boundary and do not replace review.

Before staging changes, contributors must review:

```bash
git status --short
git diff --cached --name-only
```

Generated artifacts must not be force-added.

## Incident Response

If a prohibited artifact is committed:

1. Stop distribution of the affected branch or repository.
2. Remove the artifact from the current tree.
3. Identify the data classes and affected people or clients.
4. Rotate any exposed credentials.
5. Purge the artifact from Git history using an approved administrative
   procedure such as `git filter-repo`.
6. Force-push rewritten history only after Security, DevOps, and repository
   owner approval.
7. Notify all clone owners to re-clone after the rewrite.
8. Record the incident and validation evidence.

Sprint 5.1 removes `project_structure.txt` from the current repository tree.
Because history rewriting affects every clone and remote reference, the
historical purge remains a controlled repository-administration action and is
not performed by this feature branch.

## Validation

Repository review must confirm:

- No tracked operational databases, recordings, transcripts, or reports.
- No generated repository dumps.
- No real customer or employee data in templates or documentation.
- Secret scanning passes.
- New artifact patterns are added to `.gitignore` when discovered.
