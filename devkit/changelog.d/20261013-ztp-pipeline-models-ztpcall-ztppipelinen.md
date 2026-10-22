---
kind: added
title: ZTP pipeline models: ZtpCall, ZtpPipelineNode, ZtpNodeDetail, ZtpPipelineSummary
audience: developer
refs: #314
---
`ZtpCall` lists a device that fetched its bootstrap, with its `stage` (`ZtpCallStage`) and `attempts`. `ZtpPipelineNode` and `ZtpNodeDetail` show a node's `stage` (`ZtpStage`), `readiness` (`ZtpAssetReadiness`), `stalled` reason, `discoveries` and `provision_jobs`; `ZtpPipelineSummary` counts nodes per stage and approved assets in the `pool`.
