# Checklist for the first real iBOS switch

Everything the driver has been built against is either read in a document, read in Oxidized, or assumed. This list turns
the assumptions into answers. Work through it in order. It is read-only until the last section, and the last section only
runs on a lab switch that nobody depends on.

Fact ids refer to [evidence.md](evidence.md). When you know the answer, change the entry in `evidence/register.toml`
(level, basis, sources), regenerate the matrix, and fix the mock and the tests that assumed something else.

## Before you touch anything

- Written agreement from the owner of the switch for what you are about to do, and which account you may use.
- Use the account ACEX will use, not an administrator's. If it cannot do something, that is a finding.
- Read-only commands only until section 6. Do not paste or save an output before it has been checked for secrets
  (section 5), and keep unmasked captures on your own machine only.
- One wrong password attempt at most. Accounts lock.
- Record for every capture: the model, the firmware image, the date, the command, and whether the session was in user or
  privileged mode.
- Keep raw captures byte-exact (`script`, or the debug option of the transport), not copied from a terminal window.

## 1. Connect

| Fact | Do | Record |
|---|---|---|
| `SSH-AUTH-METHODS` | `ssh -vvv` to the switch with the intended account; stop after login. | Key exchange, host key types, ciphers, offered authentication methods, whether a pty is required. |
| `LOGIN-LANDING-MODE` | Look at the first prompt. | `>` or `#`. Whether it depends on the account. |
| `PROMPT-TRAILING-SPACE` | Capture the bytes after the prompt (`ssh ... \| hexdump -C`). | Whether a space or other bytes follow `>` or `#`. |
| `LINE-ENDINGS-ANSI` | Same capture, with a command that prints several lines. | CR LF or LF, escape sequences, backspaces. |
| `SESSION-LIMITS` | Ask the owner; open two sessions. | Idle timeout, concurrent sessions allowed. |

## 2. Session behaviour

| Fact | Do | Record |
|---|---|---|
| `ENABLE-WRONG-PASSWORD` | Only if the owner agrees: one wrong enable password. | The exact answer, and whether the session stays usable. |
| `PAGER-BEHAVIOUR` | Run a long command (`show running-config`) before `terminal no pager`. | What the pager prints and how it is dismissed. Then send `terminal no pager` and `terminal width 65535` and note the answers. |
| `ERROR-FORMAT` | Send a misspelled command, an incomplete one (`show`) and one with a bad argument (`show version x`). | All three answers, byte-exact. |

## 3. Read-only commands

Run each in user mode and in privileged mode, and record whether it is accepted.

| Fact | Command | Record |
|---|---|---|
| `SHOW-VERSION-ASR6000`, `SHOW-VERSION-MS4K-635`, `SHOW-VERSION-7X` | `show version` | The whole output for the model you have. Compare with the fixture of that model. |
| `RUNCFG-MS4K-630`, `RUNCFG-7X-REJECTED`, `RUNCFG-7X-AFTER-ENABLE` | `show running-config` in user mode, after `enable`, and `show running-configuration` | The three answers. If it is rejected, record the firmware and the exact error. |
| `RUNCFG-ORDER-MS4K`, `RUNCFG-BLOCK-SEPARATOR` | `show running-config` | The whole output. Where the hostname line sits, what separates stanzas, whether it ends with `!end`. |
| `RUNCFG-DOC-INDENT-ARTIFACT` | The same output | Whether any line is indented differently from its neighbours, and how `tengigabitethernet` ports are spelled. |
| `INTERFACE-DISABLED-FORM` | `show running-config` on a switch with a port that is shut down | The lines of a disabled port, and of a port that was never configured. |
| `SHOW-LLDP` | `show lldp neighbors`, `show lldp neighbours`, `show pfdp neighbours` | Which exist, and their layout. |

## 4. Facts the tests assumed from layouts

If the model you have is not one of the three in the fixtures (ASR6000, MS4000, MS7048-AC), capture its `show version`,
`show running-config` and `show vlan` as well, and add a fixture and a scenario for it.

## 5. Secrets

| Fact | Do | Record |
|---|---|---|
| `SECRET-SYNTAX-OTHER` | Search a capture for `password`, `secret`, `key`, `community`, `md5`, `encrypted`, `hash`, long base64-looking strings. Run the kit's check on it: `python -c "from ibos_kit.masking import find_unmasked; import sys; print(find_unmasked(open(sys.argv[1]).read()))" capture.txt`. | Every line shape that carries a secret, with the value replaced. Add a rule for each to the driver and to the kit. |

Do not share a capture before every shape in it is masked and a second person has looked.

## 6. Configuration mode: only on a lab switch

Stop here unless the vendor's command reference for the firmware is open next to you.

| Fact | Do | Record |
|---|---|---|
| `CONFIG-MODE-ENTRY` | Enter configuration mode the way the reference says. | The command, the prompt in each mode, how to leave. |
| `CONFIG-ERROR-FEEDBACK` | Send one valid and one invalid line. | The answer to each, and whether the valid one was applied. |
| `CONFIG-SAVE-COMMIT` | Change a harmless description, save it the way the reference says, reload the switch. | Whether it is live at once, how it is saved, whether a reload keeps it, whether there is a rollback. |

Then change `allow_unverified_config_mode` from a switch you flip by hand into the real behaviour, and replace the
experimental profile of the mock with a verified one.

## What to send back

The register entries you changed, the raw captures (masked, checked), and a list of what differs from the mock. That list
is the first real bug list of the driver.
