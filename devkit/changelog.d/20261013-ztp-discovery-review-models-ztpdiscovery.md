---
kind: added
title: ZTP discovery review models: ZtpDiscoveryResponse, proposal, bulk approve/reject
audience: developer
refs: #314
---
`ZtpDiscoveryResponse` carries the device's self-reported facts, `review_status` (`ZtpReviewStatus`), `conflicts` (`ZtpConflict`, `ZtpConflictKind`) and a `proposal` (`ZtpApprovalProposal`, with an `action` and a `hash` echoed back as `proposal_hash` in `ZtpApproveRequest`). `ZtpBulkApprove` (with `dry_run`), `ZtpBulkReject` and `ZtpBulkResult` cover bulk review.
