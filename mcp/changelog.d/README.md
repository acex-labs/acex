# Changelog fragments for the MCP server

One file per change, written for the people who ask an AI assistant about ACEX and the administrators who run the server: what they now see, type or must set. Add one with your pull request; CI fails a pull request that changes this package without one. The files are compiled into `src/acex_mcp/changelog.json` when a release is cut, which stamps the version and date, so never edit that file. The backend image build copies the compiled file, and the notes appear under Settings > What's new.

```
python scripts/changelog.py new mcp --kind added --title "A tool answers which nodes are awaiting approval"
```

Same format and rules as the backend's: see `backend/changelog.d/README.md` and `docs/guides/changelog.md`. Entries are for `audience: user` unless they are written for someone else; `internal` satisfies the check for work nobody can notice.
