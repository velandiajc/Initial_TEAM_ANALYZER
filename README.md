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
-> Discovery Layer
-> Repositories
-> Analytics Services
-> Insight Generation
-> Markdown Reports

## Supported Survey Files

TEAM_ANALYZER supports channel-aware CSV survey ingestion for:

- Phone Call survey exports
- Chat survey exports

Place CSV files in:

```text
Data/raw/surveys/
```

The latest CSV file in that folder is processed automatically. Runtime data, CSVs, SQLite databases, reports, and local tool workspaces are not committed.

## Run

```bash
python main.py
```

To clear generated database and report outputs before running:

```bash
python main.py --reset
```
