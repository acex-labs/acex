# Guide: building the iBOS driver with the kit

You are going to write a driver for Waystream iBOS switches without having a switch. The kit gives you a stand-in
that speaks SSH on your own machine, outputs shaped like the real ones, and tests that tell you when each piece of the
driver is done. You write the driver; the kit does not contain it.

Read this page once, then work through [exercises.md](exercises.md) in order.

## What a driver is made of

A driver in ACEX is four small classes tied together by a fifth. Their base classes are in
[`devkit/src/acex_devkit/drivers/base.py`](../../devkit/src/acex_devkit/drivers/base.py); the Cisco IOS driver in
[`drivers/cisco_ios_cli/`](../../drivers/cisco_ios_cli/src/acex_driver_cisco_ioscli) is a finished example to read.

| Class | Job | Holds device state? | You write it in |
|---|---|---|---|
| `Transport` | Opens the SSH session, sends commands, returns text. The only class that talks to a switch. | Yes, one per session | Exercises 2, 3, 8 |
| `Codec` | Turns configuration text into the model and back. Pure: no network, no device. | No | Exercises 4, 5, 6, 8 |
| `BaseNormalizer` | Rules that drop noise lines and mask secrets. The codec calls it. | No | Exercises 4, 5 |
| `State` | Reads facts such as model and serial number out of show commands. | No | Exercise 7 |
| `NetworkElementDriver` | Names the four classes and the platforms the driver supports. | No | Given |

Two rules shape everything:

1. The codec never talks to a device and the transport never interprets configuration. A parser can be tested with a
   text file; a transport can be tested with a mock.
2. A configuration exists in three forms (raw, normalized, parsed), and each is tested on its own. See
   [architecture.md](architecture.md#three-forms-of-a-configuration).

## Set up

You need Python 3.13 and a checkout that has the `devkit/` folder next to `waystream-kit/`.

```bash
cd waystream-kit
./scripts/setup.sh                 # creates .venv, installs the devkit and the kit
.venv/bin/python -m pytest         # the kit's own tests: all green
.venv/bin/python -m pytest exercise   # your exercises: red until you write the code
```

If `python3.13` is not on your path, use `PYTHON=python3 ./scripts/setup.sh`.

The exercise tests start a mock on a free loopback port by themselves. You do not need a running mock to run them.

## See the device first (Exercise 1)

Start a mock in one terminal:

```bash
.venv/bin/python -m ibos_kit.mock --list          # the scenarios
.venv/bin/python -m ibos_kit.mock b               # MS4000, lands in privileged mode
```

Connect from a second terminal. These options keep your own SSH setup untouched: no config file, no known hosts, no
keys.

```bash
ssh -F /dev/null -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no \
    -o PubkeyAuthentication=no -p 2222 lab@127.0.0.1
```

The password is printed when the mock starts, and is also `lab-password-not-secret`. Try `show version`,
`show running-config`, `sh vlan`, a misspelled command. Then start scenario `d` and `e` and see what is different. The
mock prints a log line for every command saying how well that answer is known.

```bash
.venv/bin/python -m ibos_kit.mock d --explain     # what is verified, inferred and assumed in scenario d
```

## How to read the evidence

Everything the mock does rests on an entry in [evidence.md](evidence.md):

- VERIFIED: a source we have read says so. The basis tells which: a manufacturer document, the third-party Oxidized
  model, or a real device (none yet).
- INFERRED: derived from something that does not say it directly, for example one user report.
- UNKNOWN: nobody has shown us. Where the mock answers anyway, the entry is marked as assumed.

Before you write code for a behaviour, look up its entry. If it is UNKNOWN, write the code so that it fails loudly or
keeps working when the real device turns out different, and add the fact to the list for the day a real switch is
available ([real-device-checklist.md](real-device-checklist.md)). When you learn something new, add or change an entry in
`evidence/register.toml` and run `python -m ibos_kit.evidence`; a test checks that the matrix is up to date.

## How to work

- One exercise at a time. Its test file names the tests that must pass. Read them: they are the specification.
- Make a test pass with the smallest change, then clean up. Commit after each exercise in your fork.
- When something is not in the tests, look in the Cisco driver for how the same thing is done there.
- Do not copy Cisco behaviour for configuration mode, saving or committing. Nobody has shown how iBOS does it. Exercise 8
  is built around that gap on purpose.
- Keep comments and docstrings out of the code unless the reason for a line is not obvious. Put explanations in your notes
  or in the guide.

## Where the driver goes afterwards

The exercise package is laid out like a real driver (`acex_driver_waystream_ibos`). When the devkit has the vendor and OS
for Waystream, the files move to `drivers/waystream_ibos_cli/src/acex_driver_waystream_ibos/` next to a `pyproject.toml`
modelled on the Cisco one, with an `acex.neds` entry point. The tests stay as they are and the transport tests keep using
the mock. That move, and the pull request, are separate steps and not part of the exercises.

## Common traps

- A scrapli prompt given to an interactive send is matched literally unless it starts with `^` and ends with `$`.
- If `open()` fails after the SSH connection is up, close the connection before raising. The tests check that nothing is
  left behind.
- A truncated answer must never be returned as if it were complete. Raise instead.
- Unknown syntax is data. A driver that silently drops lines it does not understand makes a diff look clean.
- Keep the raw configuration raw. Normalizing and masking are separate steps on a copy.
