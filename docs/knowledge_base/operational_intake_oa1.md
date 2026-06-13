# OA-1 Operational Intake

OA-1 creates the first operational entry point for CSAT exports.

The intake workflow is intentionally narrow:

- Read one supervisor-provided CSAT export from the CLI.
- For Excel workbooks, discover the CSAT source sheet by required columns.
- Project only hardcoded allow-listed fields.
- Classify each response as Promoter, Neutral, or Detractor.
- Rank detractor drivers by operational priority.
- Persist the run, projected records, rankings, and parity report.

## Allow-Listed Projection

Only these canonical fields are allowed into Operational Intake persistence:

- contact_id
- agent_id
- agent_name
- score
- survey_date
- brand
- media_type
- driver
- sub_driver
- csat_category
- disposition

Customer comments and raw payloads are not part of OA-1 persistence.

## Excel Sheet Discovery

Excel workbooks are not processed from the first sheet by default. Intake scans
workbook sheets and selects the first sheet with the required CSAT source
columns:

- contactid
- OSAT
- agentname or Agent Clean
- Driver_Tag
- Sub_Driver
- CSAT Category (Auto)

If no sheet contains these fields, intake fails with a validation error.

## Driver Mapping

OA-1 maps operational driver fields directly from the source workbook:

- driver: Driver_Tag
- sub_driver: Sub_Driver
- csat_category: CSAT Category (Auto)

## Detractor Classification

Scores use the existing CSAT/OSAT survey scale:

- Promoter: score >= 9
- Neutral: score >= 7 and score < 9
- Detractor: score < 7

## Impact Score

Each detractor record receives an impact score of:

`10 - score`

Promoter and Neutral records receive an impact score of `0`.

Driver-level impact score is the sum of detractor record impact scores for that
driver.

## Priority Ranking

Priority ranking is deterministic:

1. Detractor count descending.
2. Impact score descending.
3. Driver name ascending.

Impact ranking is deterministic:

1. Impact score descending.
2. Driver name ascending.

## Parity Report

Each run creates a Markdown parity report in `/Reports` and persists the report
content in SQLite as a historical artifact.

The report includes field-level parity counts and mismatch details for:

- classification
- driver
- sub_driver
- csat_category
