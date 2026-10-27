# Changelog fragments for the collection agent

One file per change, written for the administrators who deploy the agent and the engineers who rely on what it collects: what they now see, type or must set. Add one with your pull request; CI fails a pull request that changes this package without one. The files are compiled into `src/acex_collection_agent/changelog.json` when a release is cut, which stamps the version and date, so never edit that file. The backend image build copies the compiled file, and the notes appear under Settings > What's new.

```
python scripts/changelog.py new agents/collection-agent --kind added --title "Routes are collected every five minutes"
```

Same format and rules as the backend's: see `backend/changelog.d/README.md` and `docs/guides/changelog.md`. Entries are for `audience: admin` unless they are written for someone else; `internal` satisfies the check for work nobody can notice.
