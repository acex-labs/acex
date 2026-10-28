# Changelog

## Unreleased

### Added

- Added paginated CVE storage and management endpoints, including bulk
  ingestion and CVSS base severity, plus shared CVE models and client resources.
- Added asynchronous vendor CVE discovery from the NVD API, with paginated
  requests, rate limiting, retries, and worker queue integration.
- Added encrypted backend storage and authenticated API operations for the
  NVD API key.
