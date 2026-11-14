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
| `d-ms4000-630` | MS4000, 6.3.0-ED-R. Asks for an enable password; the commands of the installation guide. SSH on 6.3.0 is an assumption |
| `e-ms7048-762` | MS7048-AC, 7.6.2-GD-R, ports named `ethernet1/1`. `show running-config` is refused until `enable`, as one user report describes and the manual explains |
| `e-ms7048-762-never` | A hypothetical fault: the same, refused even after `enable` |
| `f-failures` | An MS4000 with faults you switch on: `--hang-on`, `--drop-after-lines`, `--latency-ms`, `--reject-logins`, `--legacy-kex-only` |

Every scenario lands in user mode, as a default account does; `show running-config` needs `enable`. `--start-mode privileged`
starts in admin mode like an account with privilege admin, and `--prompt-trailing-space` adds a space after the prompt.
`--experimental-config-mode` adds the configuration mode the command reference describes, which nobody has tried on a
device; it says so in the greeting and the log.
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
