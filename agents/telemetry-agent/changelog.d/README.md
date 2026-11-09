# Changelog fragments for the telemetry agent

One file per change, written for the administrators who deploy the agent next to Telegraf: what they now see, type or must set. Add one with your pull request; CI fails a pull request that changes this package without one. The files are compiled into `src/acex_telemetry_agent/changelog.json` when a release is cut, which stamps the version and date, so never edit that file. The backend image build copies the compiled file, and the notes appear under Settings > What's new.

```
python scripts/changelog.py new agents/telemetry-agent --kind added --title "The agent acknowledges a revision after Telegraf reloads"
```

Same format and rules as the backend's: see `backend/changelog.d/README.md` and `docs/guides/changelog.md`. Entries are for `audience: admin` unless they are written for someone else; `internal` satisfies the check for work nobody can notice.
