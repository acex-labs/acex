# Changelog fragments for the CLI

One file per change, written for the network engineers who type the commands: what they now see, type or must set. Add one with your pull request; CI fails a pull request that changes this package without one. The files are compiled into `src/acex_cli/changelog.json` when a release is cut, which stamps the version and date, so never edit that file. The backend image build copies the compiled file, and the notes appear under Settings > What's new.

```
python scripts/changelog.py new cli --kind added --title "The `jobs list` command shows failed jobs first"
```

Same format and rules as the backend's: see `backend/changelog.d/README.md` and `docs/guides/changelog.md`. Entries are for `audience: user` unless they are written for someone else; `internal` satisfies the check for work nobody can notice.
