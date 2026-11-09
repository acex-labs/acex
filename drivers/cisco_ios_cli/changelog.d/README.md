# Changelog fragments for the Cisco IOS CLI driver

One file per change, written for the network engineers who use ACEX: what
they now see on the device or in the differences ACEX reports. Add one with
your pull request; CI fails a pull request that changes this driver without
one. The files are compiled into
`src/acex_driver_cisco_ioscli/changelog.json` when a release is cut, which stamps the version
and date, so never edit that file. The notes appear under Settings > What's new.

```
python scripts/changelog.py new drivers/cisco_ios_cli --kind fixed --title "Interface descriptions with spaces are sent correctly"
```

Same format and rules as the backend's: see `backend/changelog.d/README.md` and
`docs/guides/changelog.md`. `internal` satisfies the check for work users
cannot notice (refactoring, tests, a dependency bump).
