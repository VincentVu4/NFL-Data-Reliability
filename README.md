# NFL Data Reliability Platform

An automated data engineering platform that ingests live NFL scoreboard data, preserves immutable raw snapshots, validates and quarantines malformed records, detects game-state changes, and raises reliability alerts when live data becomes stale.

The project is designed to model a production data pipeline rather than a one-time sports analysis. Its focus is data quality, observability, fault tolerance, and reproducible processing.

## Why This Project Exists

Real-time data feeds can fail in ways that are not obvious. An API may return a successful HTTP response while still providing incomplete, duplicated, malformed, or stale data. This pipeline monitors both delivery and data quality so downstream analytics do not blindly trust an unhealthy feed.

## Current Capabilities

- Extracts real NFL scoreboard data from ESPN with timeouts, retries, and HTTP error handling
- Saves timestamped raw JSON snapshots for replay and auditing
- Parses nested API responses into flat game-level records
- Validates required identifiers, teams, scores, game states, and data types
- Quarantines malformed and invalid records with rejection reasons
- Writes valid records to Parquet with UTC timestamps and preserved data types
- Generates SHA-256 fingerprints for game-state comparison
- Classifies snapshots as `NEW`, `CHANGED`, or `UNCHANGED`
- Detects potentially stale live games using configurable thresholds
- Produces deterministic reliability-alert identifiers for downstream deduplication
- Records pipeline status, duration, file locations, and record counts in an audit log
- Writes structured operational logs to the terminal and a log file
- Uses environment-based configuration for local and future cloud execution
- Includes unit and mocked end-to-end tests with pytest

## Pipeline Architecture

```text
ESPN NFL Scoreboard API
          |
          v
Retry-aware extraction
          |
          +--------------------> Raw JSON snapshots
          |
          v
Fault-tolerant parsing
          |
          v
Validation
     /          \
    v            v
Valid games    Rejected games
    |            |
    v            v
Parquet       Quarantine JSON
    |
    v
Change detection
    |
    v
Stale-feed alerts + pipeline audit records
```

## Technology Stack

| Area | Technology |
|---|---|
| Language | Python 3.12 |
| API ingestion | Requests |
| Transformation | pandas |
| Analytical storage | Apache Parquet / PyArrow |
| Testing | pytest |
| Configuration | python-dotenv |
| Version control | Git and GitHub |
| Planned cloud storage | Azure Data Lake Storage Gen2 |
| Planned processing | Azure Databricks and Delta Lake |
| Planned reporting | Power BI |

## Repository Structure

```text
nfl-data-reliability/
|-- src/
|   |-- __init__.py
|   |-- config.py
|   |-- pipeline.py
|   `-- validation.py
|-- tests/
|   |-- test_games.py
|   `-- test_pipeline_e2e.py
|-- data/                  # Generated locally and excluded from Git
|   |-- raw/
|   |-- processed/
|   |-- quarantine/
|   |-- alerts/
|   |-- audit/
|   `-- state/
|-- logs/                  # Generated locally and excluded from Git
|-- .env.example
|-- .gitignore
|-- requirements.txt
`-- README.md
```

## Getting Started

### 1. Clone the repository

```powershell
git clone <repository-url>
cd nfl-data-reliability
```

### 2. Create and activate a virtual environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Create local configuration

```powershell
Copy-Item .env.example .env
```

### 5. Run the pipeline

```powershell
python -m src.pipeline
```

### 6. Run the test suite

```powershell
python -m pytest -v
```

## Data Layers

| Layer | Output | Purpose |
|---|---|---|
| Raw / Bronze | Timestamped JSON | Preserves the source response exactly as received |
| Processed / Silver | Parquet game snapshots | Provides typed, validated, flattened records |
| Quarantine | JSON rejected records | Preserves invalid data and rejection reasons |
| Operational | Audit, state, alerts, and logs | Supports monitoring, troubleshooting, and change detection |

## Reliability Rules

The current validation layer checks for:

- Missing game, team, or schedule identifiers
- Invalid season and week types
- Identical home and away teams
- Invalid or negative scores
- Unexpected game states
- Missing or malformed nested API structures
- Live games that remain unchanged beyond the configured stale threshold

## Testing Strategy

Unit tests cover validation, hashing, state classification, stale-feed detection, and alert creation. A mocked end-to-end test replaces the live API call with controlled ESPN-shaped data and verifies that the complete pipeline produces raw, processed, state, and audit outputs inside an isolated temporary directory.

## Roadmap

- Store raw and processed datasets in Azure Data Lake Storage Gen2
- Orchestrate scheduled ingestion during live NFL windows
- Transform snapshots into Bronze, Silver, and Gold Delta tables in Databricks
- Add play-by-play ingestion and sequence-quality checks
- Add a secondary provider for cross-source score and status comparisons
- Publish freshness, completeness, rejection, and latency metrics to Power BI
- Add CI checks for tests and code quality

## Project Status

The local ingestion and reliability foundation is complete. Azure storage, Databricks transformations, scheduling, play-by-play ingestion, cross-source validation, and Power BI reporting remain roadmap work and are not represented as completed features.

## Data Source Note

This project uses a publicly accessible ESPN JSON endpoint for educational and portfolio purposes. The endpoint is not represented as an officially supported public ESPN API and may change without notice. That instability is treated as a realistic reliability-engineering constraint.
