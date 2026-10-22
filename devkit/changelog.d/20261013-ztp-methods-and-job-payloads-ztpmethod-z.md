---
kind: added
title: ZTP methods and job payloads: ZtpMethod, ZtpMethodResponse, ZtpDiscoverData
audience: developer
refs: #312, #314
---
New module `acex_devkit.models.ztp` with `ZtpMethod` (currently `cisco_iosxe_python`), `ZtpMethodResponse` and `ZtpMethodUpdate` (per-method `ned` and bootstrap login, only sent fields change), and the job payloads `ZtpDiscoverData`, `ZtpDiscoverResult`, `ZtpProvisionData` and `ZtpProvisionResult`. New methods are added to `ZtpMethod` and `ZTP_METHOD_INFO` together.
