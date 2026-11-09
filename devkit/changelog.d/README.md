# Changelog fragments for the devkit

One file per change, written for the developers who build on it: name the model, field, resource or method that changed, and say what a caller must do. Add one with your pull request; CI fails a pull request that changes this package without one. The files are compiled into `src/acex_devkit/changelog.json` when a release is cut, which stamps the version and date, so never edit that file. The notes appear under Settings > What's new.

```
python scripts/changelog.py new devkit --kind changed --title "A node's provision status has a new value"
```

Same format and rules as the backend's: see `backend/changelog.d/README.md` and `docs/guides/changelog.md`. Set `audience: developer` on every entry here, and `breaking: true` when a caller must change something; `internal` satisfies the check for work callers cannot notice.
