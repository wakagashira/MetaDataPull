# Changelog

## [0.1.1] - First Minor Release
- Promoted from 0.0.x to 0.1.x to mark stable field syncing functionality
- Includes fixes for `sf force schema` commands and correct JSON parsing
- SQL upsert logic working reliably with autocommit

## [0.0.8] - JSON Parsing Fix
- Fixed `get_fields` to parse fields from `result.fields` instead of top-level
- Fixed `get_objects` to parse from `result` array
- Ensures fields are now captured correctly

## [0.0.7] - Force Schema Fix
- Hardcoded CLI commands to always use `sf force schema ...`
- Ensures fields are returned and written to SQL
- Still skips MetadataComponentDependency (not supported in this CLI)

## [0.0.6] - CLI Compatibility
- Updated CLI calls to use `sf force schema ...` instead of `sf schema ...`
- Disabled MetadataComponentDependency sync (not supported in this CLI)
- Focused only on pulling object fields into SQL reliably

## [0.0.5] - CLI Fix
- Updated CLI commands to use new syntax (`sf schema sobject ...`)
- Added centralized runner with error handling (`run_sf_command`)
- Prints warnings if CLI fails or returns no fields
- Connection now uses `autocommit=True` for reliability

## [0.0.4] - Reliable Inserts & Debugging
- Fixed UPSERT to check `rowcount <= 0` (previously may skip inserts)
- Added null safety (`label or ""`, `dtype or ""`)
- Added debug prints for each INSERT/UPDATE
- Changed commit strategy: commit once per object (faster, safer)
- Commit once after dependencies instead of per row

## [0.0.3] - UPSERT Fix
- Replaced MERGE with safer UPSERT logic (UPDATE first, then INSERT if no rows updated)
- Ensures fields and dependencies actually get inserted into SQL reliably

## [0.0.2] - Field Usage Tracking
- Added support for syncing field usage (MetadataComponentDependency)
- New SQL table: SalesforceFieldUsage
- Captures where each field is referenced (flows, layouts, validation rules, etc.)
- Added `.env.example` file for safe version control

## [0.0.1] - Initial Release
- First working version of Salesforce → SQL field sync
- Creates SalesforceFields table automatically
- Pulls all objects + fields using Salesforce CLI
- Stores into SQL Server with upsert logic
- Tracks deletions with IsDeleted flag
- Configurable via .env (DB + Org alias + CLI path)
- Added run_sync.bat for Windows double-click execution
