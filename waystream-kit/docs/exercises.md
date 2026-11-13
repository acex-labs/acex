# Exercises

Eight exercises, in order. Each says what to build, which classes and methods you will meet, which evidence to read
first, and which tests tell you it is done. None of them contains the answer: the hints say where to look, not what to
write.

Run one exercise's tests with `.venv/bin/python -m pytest exercise/tests/test_ex2_transport.py`. Exercise 8 has two tests
that are skipped unless you ask for them: add `-m experimental`.

The code you change is in `exercise/src/acex_driver_waystream_ibos/`.

A few tests are green before you write anything (the environment checks of Exercise 1 and some guards in Exercises 4 and
5, such as "masking twice changes nothing"). They are there so that your code does not break them.

## Exercise 1: See the device

Goal: know what the thing you are about to talk to looks like.

- Start scenarios `b`, `d` and `e`, one at a time, and log in with `ssh` as the guide shows.
- Answer in your notes: What does the prompt look like in each? Which scenario lands in user mode? What does `enable` ask
  for? What does a wrong command look like, and where do the carets point? Which lines of `show running-config` start
  with `!volatile` in scenario `c`?
- Read [evidence.md](evidence.md), the VERIFIED table, and mark which of your answers are verified and which the mock
  only assumes.

Done when: `pytest exercise/tests/test_ex1_environment.py` is green and your notes answer the questions.

## Exercise 2: Transport, open and execute

Goal: open an SSH session to a switch, get it ready for scripted use, run commands and return their output.

Classes and methods: `IbosTransport` in `transport.py` (`open`, `close`, `execute`), the credentials on `self.credentials`
(`userpass`, optionally `privilege_escalation`), the exceptions in
[`acex_devkit/exceptions`](../../devkit/src/acex_devkit/exceptions/__init__.py). The library is scrapli over asyncssh;
see how [`CiscoIOSTransport`](../../drivers/cisco_ios_cli/src/acex_driver_cisco_ioscli/transport/transport.py) opens a
session.

Evidence to read first: `PROMPT-MODES`, `PROMPT-PATTERN`, `PROMPT-TRAILING-SPACE`, `ENABLE-COMMAND`,
`ENABLE-WRONG-PASSWORD`, `TERMINAL-COMMANDS`, `LOGIN-LANDING-MODE`, `SSH-AUTH-METHODS`.

What the tests expect:

- Commands return one output per command, without the echoed command and without the final prompt.
- After login the session is in privileged mode, whichever mode the device landed in, and the two `terminal` commands
  have been sent before anything else.
- A missing or wrong enable password, a wrong login password and a device that refuses every login are
  `AuthenticationFailed`. A refused connection is `ConnectionError`. A command that never answers is `ConnectionTimeout`.
  These are the devkit's exceptions, not the library's.
- A prompt with a trailing space works. A device that offers only an old key exchange can still be reached.
- A failed `open` leaves no connection open. `close` can be called twice.

Hints:

- Look at how the prompt pattern and the timeouts are passed to the scrapli driver, and at which scrapli driver class has
  no built-in idea of privilege levels.
- Entering privileged mode may or may not ask for a password. Decide what to do in each case before you write it.
- The class attributes `PORT`, `timeout_socket` and `timeout_ops` exist so tests can change them.

Done when: `pytest exercise/tests/test_ex2_transport.py` is green.

## Exercise 3: Transport, get_config

Goal: return the running configuration exactly as the switch printed it.

Classes and methods: `IbosTransport.get_config`; `Session.get_config` in `base.py` explains who calls it and what they
expect ("Raw and unmasked").

Evidence to read first: `RUNCFG-COMMAND`, `RUNCFG-7X-REJECTED`, `RUNCFG-7X-AFTER-ENABLE`, `VOLATILE-LINES`, `PAGER-BEHAVIOUR`.

What the tests expect:

- The output is the configuration and nothing else: no prompt, no echo, no carriage returns.
- `!volatile` lines are still in it. Raw means raw.
- An error answer such as the one from scenario `e` without enable is raised as a driver error that carries the device's
  text. It is never returned as if it were a configuration.
- A connection that drops half-way is an error, not a short configuration.

Done when: `pytest exercise/tests/test_ex3_get_config.py` is green.

## Exercise 4: Normalize

Goal: make two reads of the same switch comparable by dropping lines that change for reasons that are not intent.

Classes and methods: `IbosNormalizer` in `normalizer.py`, `LineRule` and `BaseNormalizer` in
[`acex_devkit/normalizer`](../../devkit/src/acex_devkit/normalizer/__init__.py), `IbosCodec.normalize`. The Cisco
normalizer lists a dozen line rules.

Evidence to read first: `VOLATILE-LINES`, `VOLATILE-STRIPPING`, `RUNCFG-HEADER`, `RUNCFG-END-MARKER`,
`RUNCFG-BLOCK-SEPARATOR`. Then open `fixtures/golden/` and compare a raw fixture with its normalized golden file.

What the tests expect: the four golden pairs, a configuration with a client equal to one without, `!volatile` removed
wherever it sits and other comments kept, the version comment, the end marker and lone `!` separators removed, Windows
line endings accepted, and normalizing twice changing nothing.

Done when: `pytest exercise/tests/test_ex4_normalize.py` is green.

## Exercise 5: Mask secrets

Goal: produce a copy of a configuration that is safe to store and show.

Classes and methods: `RewriteRule`, `MASK` and `BaseNormalizer.mask`; `IbosCodec.mask`. The Cisco normalizer has a
list of rewrite rules to compare with.

Evidence to read first: `SECRET-SYNTAX-SNMP-RADIUS` and `SECRET-SYNTAX-OTHER`. Only three syntaxes are known. Everything
else is a guess, and a guess that leaves a secret in clear is worse than one that masks too much.

What the tests expect: the three known syntaxes masked with the devkit's `MASK`; the same number of lines; masking twice
giving the same text; no change to configurations without secrets; a hit report that names rules and never values; and
the conservative rules for the made-up syntax in `fixtures/variants/invented-secret-syntax.txt`.

Done when: `pytest exercise/tests/test_ex5_mask.py` is green.

## Exercise 6: Parse

Goal: read a normalized configuration into the model and keep a list of every line you did not understand.

Classes and methods: `Block`, `Line`, `Flag`, `Dispatch` and `Mapper` in
[`acex_devkit/drivers/mapper`](../../devkit/src/acex_devkit/drivers/mapper/syntax.py) (read the docstring of `Block`), the
hooks `Block.complete` and `Block.derive`, `ParseResult` and `UnmatchedLine` in
[`codec_result.py`](../../devkit/src/acex_devkit/models/codec_result.py), and `BLOCKS` in `syntax.py`. The Cisco
`SystemConfigSyntax` and `InterfaceSyntax` are the closest examples. A declaration in the mapper works both for parsing
and for rendering; you reuse it in Exercise 8.

Evidence to read first: `RUNCFG-INDENT`, `RUNCFG-ORDER`, `INTERFACE-NAMES`, `INTERFACE-NO-SHUTDOWN`,
`INTERFACE-DISABLED-FORM`, `RUNCFG-DOC-INDENT-ARTIFACT`.

Scope: hostname, interfaces with name, description, address and enabled. Everything else must come out as unmatched, with
the header lines it sat under. The point is not to model all of iBOS; it is to show that nothing disappears.

What the tests expect: the golden parsed files, an interface with no `no shutdown` line being neither enabled nor
disabled, raw input with `!volatile` parsing like clean input, irregular layouts neither crashing the parser nor losing a
line, unknown top-level stanzas kept with their children, and an empty configuration giving an empty result.

Done when: `pytest exercise/tests/test_ex6_parse.py` is green.

## Exercise 7: Facts

Goal: read what the device says it is out of `show version`.

Classes and methods: `parse_show_version` and `read_facts` in `state.py`; `State.get_facts` in `base.py` and the
`DeviceFacts` model in [`models/state.py`](../../devkit/src/acex_devkit/models/state.py). `get_facts` itself waits for the
devkit to know Waystream; until then the exercise stops at your own `IbosFacts`.

Evidence to read first: `SHOW-VERSION-MS4K-630`, `SHOW-VERSION-MS4K-635`, `SHOW-VERSION-7X`, `SHOW-VERSION-ASR6000`.
Three of the four are inferred or unknown. Make the parser depend on labels, not on positions.

What the tests expect: hostname, version, image, model and serial number from three layouts; a missing line giving `None`
and never an exception; an error answer not being taken for facts.

Done when: `pytest exercise/tests/test_ex7_facts.py` is green.

## Exercise 8: Render and apply (experimental)

Goal: write configuration back, with the part that nobody has shown us kept visibly apart.

Classes and methods: `IbosCodec.render`, the same `BLOCKS` as Exercise 6, `IbosTransport.apply` and
`allow_unverified_config_mode`, `ConfigurationError`.

Evidence to read first: `CONFIG-MODE-ENTRY`, `CONFIG-SAVE-COMMIT`, `CONFIG-ERROR-FEEDBACK`, `RUNCFG-ORDER`.

There are two halves. Rendering is verified syntax: the same declarations as in Exercise 6 write the lines the device
prints, in the order it prints them. Applying is not: how configuration mode is entered, left and saved is unknown, so
the mock offers a profile for it that is switched on only with `--experimental-config-mode` and announces itself as
unverified. What you build against it is a rehearsal of the shape of the code, not knowledge of the switch.

What the tests expect:

- Render writes the modelled lines, one space of indentation per level, hostname after the interfaces; what render
  writes parses back to the same model.
- `apply` refuses to write unless `allow_unverified_config_mode` has been set, and says why.
- Against a device without configuration mode the error answer is raised.
- Against the experimental profile (`-m experimental`): the payload's indentation becomes the mode changes the device
  needs, the session is left in exec mode whether or not a line was rejected, and a rejected line is raised with the
  device's text.

Done when: `pytest exercise/tests/test_ex8_render_apply.py -m "experimental or not experimental"` is green.

## After the exercises

You have a transport, a normalizer, a parser, a renderer and a facts reader that all pass against the mock. Compare your
masking rules with the kit's own in [`src/ibos_kit/masking.py`](../src/ibos_kit/masking.py). Before
anything is trusted on a customer's switch, the list in [real-device-checklist.md](real-device-checklist.md) has to be
worked through on a real device, read-only first. [limitations.md](limitations.md) says what the mock cannot tell you.
