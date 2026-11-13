# Known limitations

What the kit cannot tell you, so that a green test is not read as more than it is.

## About the device

- No real iBOS device has been used. Every VERIFIED entry rests on two manufacturer documents and Oxidized's model; the
  documents describe firmware 6.3.0 and 6.3.5 on two product lines (MS4000, ASR6000), Oxidized does not say which firmware
  it has seen.
- Firmware 7.x rests on a single, stale user report. The output of `show running-config` on 7.x has never been seen by us.
- `show version` on ASR6000 and on MS4000 6.3.5, and the position of the hostname line on MS4000, are assumptions.
- Configuration mode, saving, committing and the way configuration errors are reported are unknown. The experimental
  profile is a rehearsal with invented behaviour, not a model of the switch.
- Only some SSH facts are simulated: password authentication, one host key type, an optional old key exchange. Public
  key login, keyboard-interactive, banners, idle timeouts and session limits are not.
- There is no pager. A device that stops output with a `--More--` prompt, and the way `terminal no pager` changes that,
  are not simulated.
- Only a handful of commands exist: `show version`, `show running-config`, `show running-configuration context interface`,
  `show vlan`, `show ip interface brief`, `show clients`, `show pfdp neighbours`. Others answer with the assumed error.
- Output is deterministic: uptime is fixed, counters do not move, nothing is learned over time. Volatile lines are in the
  fixtures, they do not appear and disappear while a session is open.
- Command abbreviation is limited to the three the documents show (`sh`, `int`, `br`).

## About the kit

- Fixtures are synthetic. They follow the layout the sources show, with made-up names and documentation addresses. They
  are not copies of vendor text.
- The mock runs on loopback only, by design. A driver that works over a real network (timeouts, packet loss, slow links)
  is not tested by it, apart from the `latency_ms`, hang and drop faults.
- The full ACEX stack (backend, agent, database) is not part of the kit. Wiring the driver into a collection agent, and the
  platform declaration, wait for the devkit to know Waystream.
- The kit's own tests are not run by the repository's CI. Run `pytest` in `waystream-kit/`.
- The exercise tests check behaviour, not design. A solution can pass and still be a poor driver.

## About the evidence

- The evidence register is hand-maintained. A test checks its internal consistency (levels, bases, sources, that every
  fact the mock cites exists, that the checklist names every unknown), not that its statements are true.
- The two PDF documents were read as page images; wrapped lines in them (long image names) were joined by eye.
