---
kind: fixed
title: The compliance overview no longer stops the API while it is measured
refs: #368
---
Measuring the compliance of every node takes minutes on a large installation, and while it ran the API answered nothing else. The installation is now measured in the background, when the API starts and then every ten minutes, and `GET /api/v1/compliance` answers at once from the last measurement. The header `X-Measured-At` says when it was made. During the first minutes after a start there is no measurement yet, and the answer is 503 with a `Retry-After` of 30 seconds. Sites and regions are still measured when asked, but the API answers other requests in between.
