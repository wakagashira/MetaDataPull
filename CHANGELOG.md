# Changelog

## [0.3.6] - Namespace-aware Flow Parsing
- Added namespace detection for Flow XML files
- All tag searches are now namespace-aware (sf:field, sf:leftValueReference, etc.)
- Ensures fields are captured even when XML uses the Salesforce metadata namespace
- DEBUG_FLOW_PARSE=true will now print matched tags + text correctly
