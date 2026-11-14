# Checklist for the first real iBOS switch

Everything the driver has been built against is either read in a document, read in Oxidized, or assumed. This list turns
the assumptions into answers, and checks that what the documents say is true of the switch in front of you. Work through
it in order. It is read-only until the last section, and the last section only runs on a lab switch that nobody depends on.

Fact ids refer to [evidence.md](evidence.md). When you know the answer, change the entry in `evidence/register.toml`
(level, basis, sources), regenerate the matrix, and fix the mock and the tests that assumed something else.

## Before you touch anything

- Written agreement from the owner of the switch for what you are about to do, and which account you may use.
- Use the account ACEX will use, not an administrator's. If it cannot do something, that is a finding.
- Ask the customer, because the answers decide what is built: which firmware each switch runs (it decides between SSH and
  telnet, see `SSH-SERVER-FIRMWARE`), which product line and model (port names differ, `INTERFACE-NAMES`), whether the
  switches are managed by BECS (they then read their configuration from there, `BECS-NET-BOOT`, and a change written
  directly may be overwritten), and whether the account has privilege admin (`LOGIN-LANDING-MODE`).
- Read-only commands only until section 6. Do not paste or save an output before it has been checked for secrets
  (section 5), and keep unmasked captures on your own machine only.
- One wrong password attempt at most. Accounts lock.
- Record for every capture: the model, the firmware image, the date, the command, and whether the session was in user or
  admin mode.
- Keep raw captures byte-exact (`script`, or the debug option of the transport), not copied from a terminal window.

## 1. Connect

| Fact | Do | Record |
|---|---|---|
| `SSH-SERVER-FIRMWARE` | On a switch with firmware older than 6.3.4, try `ssh`; try telnet too. | Whether port 22 answers, and which of the two the switch offers. |
| `SSH-AUTH-METHODS` | `ssh -vvv` to the switch with the intended account; stop after login. | Key exchange, host key types, ciphers, offered authentication methods, whether a pty is required. |
| `PROMPT-TRAILING-SPACE` | Capture the bytes after the prompt (`ssh ... \| hexdump -C`). | Whether a space or other bytes follow `>` or `#`. |
| `LINE-ENDINGS-ANSI` | Same capture, with a command that prints several lines. | CR LF or LF, escape sequences, backspaces. |

## 2. Session behaviour

| Fact | Do | Record |
|---|---|---|
| `ENABLE-WITHOUT-SECRET` | On a switch with no enable secret: `enable`. | What comes back and which prompt follows. |
| `ENABLE-WRONG-PASSWORD` | Only if the owner agrees: one wrong enable password. | The exact answer, and whether the session stays usable. |
| `PAGER-PROMPT-TEXT` | On 6.3.10 or later: `terminal pager`, then `show running-config`; then `terminal no pager`. | What the pager prints at the pause and how it is dismissed. |
| `ERROR-FORMAT` | Send a misspelled command, an incomplete one (`show`) and one with a bad argument (`show version x`); also a command the account's level does not allow. | All answers, byte-exact. |

## 3. Read-only commands

Run each in user mode and in admin mode, and record whether it is accepted. The manual says the admin-level commands are
`show running-config`, `show startup-config`, `show logging` and `show tech-support`; confirm it.

| Fact | Command | Record |
|---|---|---|
| `SHOW-VERSION-ASR6000`, `SHOW-VERSION-MS4K-635`, `SHOW-VERSION-7X` | `show version` | The whole output for the model you have. Compare with the fixture of that model. |
| `RUNCFG-MS4K-630` | `show running-config` on an MS4000 with 6.3.0 | The output, or the error. |
| `RUNCFG-ORDER-MS4K`, `RUNCFG-BLOCK-SEPARATOR` | `show running-config` | The whole output. Where the hostname line sits, what separates stanzas, whether it ends with `!end`. |
| `RUNCFG-DOC-INDENT-ARTIFACT` | The same output | Whether any line is indented differently from its neighbours, and how `tengigabitethernet` ports are spelled. |
| `INTERFACE-DISABLED-FORM` | `show running-config` on a switch with a port that is shut down and one never configured | The lines of each block: is a disabled port printed with no line, or with `shutdown`? |

## 4. Facts the tests assumed from layouts

If the model you have is not one of the three in the fixtures (ASR6000, MS4000, MS7048-AC), capture its `show version`,
`show running-config` and `show vlan` as well, and add a fixture and a scenario for it. The port names of an MS 7000 are
`ethernetS/P`, those of an MS4000 `gigabitethernetN`.

## 5. Secrets

The manual lists where a secret is typed (`SECRET-SYNTAX-OTHER`); a real configuration may print more. Search a capture
for `password`, `secret`, `key`, `community`, `md5`, `encrypted`, `hash`, `license`, and long base64-looking strings. Run
the kit's check on it:

```bash
python -c "from ibos_kit.masking import find_unmasked; import sys; print(find_unmasked(open(sys.argv[1]).read()))" capture.txt
```

Record every line shape that carries a secret, with the value replaced, and add a rule for each to the driver and to the
kit. Do not share a capture before every shape in it is masked and a second person has looked.

## 6. Configuration mode: only on a lab switch

Stop here unless the vendor's command reference for the firmware is open next to you. The manual documents all of this for
MS 7000 on 7.5.2 (`CONFIG-MODE-ENTRY`, `CONFIG-SAVE-COMMIT`); the point is to see that it holds on your firmware and to find
out what the manual leaves out.

| Fact | Do | Record |
|---|---|---|
| `CONFIG-MODE-ENTRY` | `configure terminal`, `interface <port>`, `description`, `end`. | The prompt in each context, and that `end` returns to `#`. |
| `CONFIG-ERROR-FEEDBACK` | Send one valid and one invalid line. | The answer to each, and whether the valid one was applied. |
| `CONFIG-SAVE-COMMIT` | Change a harmless description, `do write memory` or `write memory`, reload the switch. | The answer to `write memory`, whether the change is live at once, whether a reload keeps it. |

Then change `allow_unverified_config_mode` from a switch you flip by hand into the real behaviour, and replace the
experimental profile of the mock with a verified one.

## What to send back

The register entries you changed, the raw captures (masked, checked), and a list of what differs from the mock. That list
is the first real bug list of the driver.
