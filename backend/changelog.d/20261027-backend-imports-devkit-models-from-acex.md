---
kind: internal
title: Backend imports devkit models from acex_devkit, not through acex.models
---
Classes that devkit defines (responses, enums and shared schemas) are imported from acex_devkit.models where they are used. The database models stay in acex.models. No behaviour changes.
