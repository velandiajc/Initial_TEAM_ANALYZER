# TEAM_ANALYZER

AI-powered Contact Center Analytics Platform

## Features

- Automatic agent discovery
- Survey ingestion
- SQLite persistence
- VOC analysis
- CSAT analytics
- PMCE reporting
- User story generation

## Architecture

Data Sources
↓
Discovery Layer
↓
Repositories
↓
Analytics Services
↓
Insight Generation
↓
Markdown Reports

## Run

Place survey CSV exports in:

```text
Data/raw/surveys/
```

The pipeline creates local runtime folders automatically:

- `Data/raw/surveys/`
- `Data/database/`
- `Reports/`

Generated data, SQLite databases, reports, CSVs, and virtual environments are ignored by Git.

```bash
python main.py
```

To clear generated database and report outputs before running:

```bash
python main.py --reset
```
