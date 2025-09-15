# SalesforceFieldSync

A Python utility to pull all Salesforce object fields into SQL Server using Salesforce CLI, keeping them up-to-date with inserts/updates/deletions.

## Features
- Uses Salesforce CLI (`sf force schema ...`) to pull object/field metadata
- Stores into SQL Server (`SalesforceFields` table)
- Auto-creates table if missing
- Marks missing fields as `IsDeleted=1`
- Skips MetadataComponentDependency (not available in this CLI version)
- Configurable via `.env` (DB + Org alias + CLI path)
- Windows batch script (`run_sync.bat`) for one-click execution
- Versioned via `VERSION` + `CHANGELOG.md`
- Includes `.env.example` (safe for git)

## Requirements
- Python 3.9+
- SQL Server with ODBC Driver 17+
- Salesforce CLI installed (`sf --version` works)

## Setup
1. Clone repo:
   ```bash
   git clone <your-repo-url> SalesforceFieldSync
   cd SalesforceFieldSync
   ```

2. Install dependencies:
   ```bash
   py -m pip install -r requirements.txt
   ```

3. Copy `.env.example` → `.env` and fill in details:
   ```bash
   cp .env.example .env
   ```

4. Login to Salesforce (first time only):
   ```bash
   sf login org --alias Prod --browser
   ```

5. Run sync:
   ```bash
   py sync_salesforce_fields.py
   ```

Or double-click `run_sync.bat` in Windows.

## Versioning
- Current version: **0.0.8**
- See [CHANGELOG.md](CHANGELOG.md) for details
- To tag a release:
   ```bash
   git tag v0.0.8
   git push origin v0.0.8
   ```
