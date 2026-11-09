# Changelog fragments for the backend

One file per change, written for the network engineers who use ACEX. Add one
with your pull request; CI fails a pull request that changes the backend
without one. The files are compiled into `src/acex/changelog.json` when a
release is cut, which stamps the version and date, so never edit that file.

```
python scripts/changelog.py new backend --kind added --title "Choose which driver a ZTP method uses"
```

gives `changelog.d/<date>-choose-which-driver-a-ztp-method-uses.md`:

```
---
kind: added
title: Choose which driver a ZTP method uses
---
Each ZTP method now has a driver setting under ZTP > Methods. Devices that
boot through that method are handled by the chosen driver.
```

- `kind`: `added`, `changed`, `fixed`, `removed`, `deprecated` or `security`.
  `internal` satisfies the check without being published, for work users
  cannot notice (CI, refactoring, tests).
- `title`: one line, at most 80 characters. Say what a user can now do or
  what behaves differently. Not the commit subject, not the branch name.
- The text after the front matter is the description, in Markdown. Optional,
  but the place for anything the user has to do or should know.
- Optional: `breaking: true`, `audience: admin|developer` (default `user`),
  `refs: #316, ADO-1234` (a label, optionally followed by a URL).

The person who cuts a release can add one sentence about it with
`release --summary "..."`; fragments never carry one.

The product's highlights and roadmap are not fragments. They are two plain
files in `src/acex/changelog/content/`, `highlights.md` (written together when
a release is cut) and `roadmap.md` (kept by one person), and editing them needs
no entry here. `python scripts/changelog.py brief` collects what the highlights
are written from; see the guide.

Full guide: `docs/guides/changelog.md`.
