# Known limitations

What the kit cannot tell you, so that a green test is not read as more than it is.

## About the device

- No real iBOS device has been used. Every VERIFIED entry rests on two manufacturer documents and Oxidized's model; the
  documents describe firmware 6.3.0 and 6.3.5 on two product lines (MS4000, ASR6000), Oxidized does not say which firmware
  it has seen.
- Firmware 7.x is described by the MS 7000 7.5.2 command reference, but the output of `show running-config` and of
  `show version` on a 7.x switch has never been seen by us; the manual's `show version` page has no example.
- `show version` on ASR6000 and on MS4000 6.3.5, and the position of the hostname line on MS4000, are assumptions.
- Configuration mode and saving are documented in the MS 7000 7.5.2 command reference but nobody has tried them on a
  device, and the manual shows no error text. The experimental profile follows the manual (prompts, `end`, `exit`, `do`,
  `write memory`) and invents the error answers.
- Only some SSH facts are simulated: password authentication, one host key type, an optional old key exchange. Public
  key login, keyboard-interactive, banners, idle timeouts and session limits are not.
- There is no pager. It is off by default and `terminal [no] pager` exists only from 6.3.10; a switch with the pager on,
  and what it prints at the pause, are not simulated.
- The mock speaks SSH only. Firmware older than 6.3.4 probably has no SSH server and can be reached only by telnet, which
  neither the mock nor the exercises offer.
- Only a handful of commands exist: `show version`, `show running-config`, `show running-configuration context interface`,
  `show vlan`, `show ip interface brief`, `show clients`, `show pfdp neighbours`. Others answer with the assumed error.
- Output is deterministic: uptime is fixed, counters do not move, nothing is learned over time. Volatile lines are in the
  fixtures, they do not appear and disappear while a session is open.
- Command abbreviation is limited to `sh`, `int` and `br`. The manual shows that any unique prefix works (`conf t`,
  `sh run`), and what an ambiguous prefix answers is not known.
- Port names follow the product line: scenario `e` uses `ethernet1/1`, the others and the golden files use
  `gigabitethernetN`. Device types and the naming of the real driver are not part of the kit.

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
- The two PDF documents of the first round were read as page images; wrapped lines in them (long image names) were joined
  by eye. The command reference was read as extracted text and its key pages checked as images.
- The command reference describes MS 7000 on 7.5.2. MS4000 and ASR6000 on 6.3.x may differ in details; its "introduced in"
  lines are the only version information we have.
