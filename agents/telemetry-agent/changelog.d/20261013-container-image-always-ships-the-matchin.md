---
kind: fixed
title: Container image always ships the matching ACEX devkit
audience: admin
refs: #290
---
The image build could end up with an older `acex-devkit` pulled from the package index instead of the bundled one, which made the agent stop at startup with an import error. The bundled devkit is now installed last, so it always wins. Rebuild or pull the image to pick this up.
