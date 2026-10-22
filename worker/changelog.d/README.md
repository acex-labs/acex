# Changelog fragments for the worker

One file per change, written for the administrators who deploy and operate workers: what they now see, type or must set. Add one with your pull request; CI fails a pull request that changes this package without one. The files are compiled into `src/acex_worker/changelog.json` when a release is cut, which stamps the version and date, so never edit that file. The backend image build copies the compiled file, and the notes appear under Settings > What's new.

```
python scripts/changelog.py new worker --kind added --title "A worker reconnects to the broker after a restart"
```

Same format and rules as the backend's: see `backend/changelog.d/README.md` and `docs/guides/changelog.md`. Entries are for `audience: admin` unless they are written for someone else; `internal` satisfies the check for work nobody can notice.
