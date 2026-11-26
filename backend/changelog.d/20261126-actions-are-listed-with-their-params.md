---
kind: added
title: Actions are listed with their params and result
audience: developer
---
`GET /api/v1/operations/actions` lists every action in devkit's `ACTIONS`:
its name, a short label, its description, the JSON schemas of its params and
result, and, for a result made of rows, which field holds them and their
columns. The GUI builds its action forms and result views from it.
