# iBOS development kit

Build and test a driver for Waystream iBOS switches without a switch: an SSH mock with firmware profiles, synthetic
fixtures, an evidence register that says how much of it is known, and eight exercises that lead to the driver.

Start with [docs/guide.md](docs/guide.md).

## Quick start

```bash
./scripts/setup.sh                       # .venv with the devkit and the kit
.venv/bin/python -m pytest               # the kit's tests
.venv/bin/python -m pytest exercise      # the exercises: red until you write the driver
.venv/bin/python -m ibos_kit.mock --list # the scenarios
.venv/bin/python -m ibos_kit.mock b      # start one on 127.0.0.1:2222
```

Log in with the synthetic account (made up for this kit, protects nothing):

| | |
|---|---|
| user | `lab` |
| password | `lab-password-not-secret` |
| enable password, where one is asked | `lab-enable-not-secret` |

```bash
ssh -F /dev/null -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no \
    -o PubkeyAuthentication=no -p 2222 lab@127.0.0.1
```

## Scenarios

| Key | What it is |
|---|---|
| `a-asr6000-635` | ASR6000, iBOS 6.3.5-ED-R, no clients connected |
| `b-ms4000-635` | MS4000, 6.3.5-ED-R, S-VLAN with UNI and NNI ports, no clients |
| `c-ms4000-635-client` | The same with a DHCP client: `!volatile` lines in the running configuration |
| `d-ms4000-630` | MS4000, 6.3.0-ED-R. Lands in user mode, asks for an enable password, the commands of the installation guide |
| `e-ms7048-762` | MS7048-AC, 7.6.2-GD-R. `show running-config` is rejected until `enable`, as one user report describes |
| `e-ms7048-762-never` | The same, rejected even after `enable` |
| `f-failures` | An MS4000 with faults you switch on: `--hang-on`, `--drop-after-lines`, `--latency-ms`, `--reject-logins`, `--legacy-kex-only` |

`--prompt-trailing-space` and `--start-mode user|privileged` change a scenario's assumptions.
`--experimental-config-mode` adds a configuration mode that nobody has verified; it says so in the greeting and the log.
`--explain` lists what is verified, inferred and assumed in a scenario.

## Boundaries

The mock listens on loopback only and refuses anything else. It runs no host command, reads no SSH configuration, keeps
no key on disk and has no real credentials. The kit changes nothing outside `waystream-kit/`.

## Contents

| | |
|---|---|
| [docs/guide.md](docs/guide.md) | How to work with the kit |
| [docs/exercises.md](docs/exercises.md) | Exercises 1 to 8 |
| [docs/architecture.md](docs/architecture.md) | Parts, the three forms of a configuration, what the mock claims |
| [docs/evidence.md](docs/evidence.md) | What is known about iBOS and how (generated) |
| [docs/real-device-checklist.md](docs/real-device-checklist.md) | What to check on the first real switch |
| [docs/limitations.md](docs/limitations.md) | What the kit cannot tell you |
| `evidence/register.toml` | The source of the evidence matrix |
| `fixtures/` | Synthetic outputs, golden files and `manifest.toml` |
| `exercise/` | The driver skeleton and the exercise tests |
