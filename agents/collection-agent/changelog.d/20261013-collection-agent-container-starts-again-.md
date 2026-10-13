---
kind: fixed
title: Collection agent container starts again after the 0.15.0 dependency update
audience: admin
refs: #290
---
The container image could end up with an older `acex-devkit` than the agent needs and stop at startup with an `ImportError` for `AgentNodeSet`. The image build now installs the bundled devkit last, so the right version is always used. Rebuild or pull the new image.
