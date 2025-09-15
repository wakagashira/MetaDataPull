# Changelog

## [0.2.1] - Sync Control Flags
- Added SYNC_FIELDS and SYNC_USAGE flags in .env
- Allows skipping field or usage sync for troubleshooting
- Defaults to both true

## [0.2.0] - Tooling API: Field Usage
- Added Tooling API integration using the existing sf CLI auth
- Syncs MetadataComponentDependency into SalesforceFieldUsage
- requirements.txt now includes `requests`
