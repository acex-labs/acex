---
kind: changed
title: Compliance models cover configuration and software
audience: developer
refs: #368
---
`ComplianceResult` and `SiteComplianceResult` are replaced by `NodeCompliance`, `SiteCompliance`, `ComplianceSummary` and `ComplianceOverview`, each with a configuration and a software section. New models describe the software policy (`SoftwarePolicyCreate`, `SoftwarePolicyUpdate`, `SoftwarePolicyResponse`, `SoftwareVersionInUse`) and the platform catalog (`PlatformCatalog`). `Diff.compliance_percentage` is 100.0 when nothing is desired, and `PaginatedResponse.limit` may be None.
