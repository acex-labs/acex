# Evidence matrix

Generated from `evidence/register.toml` by `python -m ibos_kit.evidence`. Edit the register, not this file.

## Sources

| Id | Kind | Source | Read |
|---|---|---|---|
| S1 | manufacturer-doc | [Waystream SKA/SEC Certifiering (published by SSNF)](https://www.ssnf.org/globalassets/nat-i-varldsklass/sakerhet/ska/certifierade-produkter-dokument-pdf/ska-sec-waystream.pdf) | 2026-11-13; pages 5-9 rendered to images and read as images (text extraction fragments the tables); not copied, fixtures are synthetic |
| S2 | manufacturer-doc | [MS4000 Installation Guide, chapter Troubleshooting iBOS](https://netcon.store/media/pdf/98/30/06/MS4000-Installation-Guide_compressed.pdf) | 2026-11-13; printed pages 26-29 (PDF pages 30-33) rendered to images and read as images |
| S3 | third-party-driver | [Oxidized model ibos.rb](https://github.com/ytti/oxidized/blob/4d6dcd671284/lib/oxidized/model/ibos.rb) | 2026-11-13; commit 4d6dcd671284 (2026-11-13) of the file, master at 52c7767f5381; previous change of the file 3f4c2ec01fcc (2024-10-16) |
| S4 | third-party-report | [Oxidized issue 2774, Problem with Waystream switches (IBOS)](https://github.com/ytti/oxidized/issues/2774) | 2026-11-13; opened 2023-04-28, one comment, closed 2023-07-19 as not planned (label Stale); no confirmed fix |
| S5 | real-device | none | no real iBOS device has been reachable during this work |

## VERIFIED (23)

| Id | Basis | Sources | Statement |
|---|---|---|---|
| PROMPT-MODES | manufacturer-doc | S1 p5-9; S2 p26-29 | The prompt is the hostname followed by > in user mode and # in privileged mode (ms>, ms#, MS4k#, ASR6K-SKA-Test#). |
| PROMPT-PATTERN | third-party-driver | S3 | Oxidized finds the prompt with ^([\w.@()-]+[#>]\s?)$, so the hostname part may hold letters, digits, underscore, dot, at, parentheses and hyphen. |
| LOGIN-NO-DEFAULT-CREDENTIALS | manufacturer-doc | S2 p26 | On the console an unconfigured switch has no default user name or password: Enter at both prompts. Once authentication is configured the right credentials are needed. This says nothing about SSH. |
| ENABLE-COMMAND | third-party-driver | S3 | enable exists. Oxidized sends it plain, or answers a Password: prompt after it (^[pP]assword:) when an enable password is configured. |
| TERMINAL-COMMANDS | third-party-driver | S3 | terminal no pager and terminal width 65535 are sent after login on every iBOS device Oxidized handles, so a pager exists and both commands are accepted (at least on the firmware Oxidized users run). |
| COMMAND-ABBREVIATION | manufacturer-doc | S2 p29 (sh vlan); S1 p6 (sh ip int br) | Commands can be abbreviated at least as sh, int and br. The rule behind it (unique prefix?) is not stated. |
| RUNCFG-COMMAND | manufacturer-doc | S1 p5 (ASR6000); S1 p9 (MS4000); S3 | show running-config prints the configuration on ASR6000 and MS4000 on iBOS 6.3.5-ED-R. |
| RUNCFG-HEADER | manufacturer-doc | S1 p5; S1 p9 | The output starts with one comment line '! version <image> (<image>.bz2)', for example ibos-asr6k-6.3.5-ED-R. |
| RUNCFG-INDENT | manufacturer-doc | S1 p5-6; S1 p9 | Lines inside an interface are indented by one space. Interface blocks are separated by a blank line in the document. |
| RUNCFG-ORDER | manufacturer-doc | S1 p5-6 | On the ASR6000 example the order is interfaces (loopback, gigabitethernet, tengigabitethernet, downstream), router ospf, hostname, access-list, service-definition, service-selection, then '!end'. Hostname is a top-level line written after the interfaces. |
| RUNCFG-END-MARKER | manufacturer-doc | S1 p6 | The ASR6000 example ends with the line '!end' before the prompt. |
| VOLATILE-LINES | manufacturer-doc | S1 p6 (ASR6000); S1 p9 (MS4000) | Lines that a script or DHCP snooping adds at run time are printed with a leading '!volatile' after the indentation, for example '!volatile policy-map vid 2 snpa <mac> <ip>/32 seq 10 policy' and '!volatile interface arp entry <ip> <mac> client'. They vanish when the client does. |
| VOLATILE-STRIPPING | third-party-driver | S3 | Oxidized deletes every line that contains '!volatile' before it stores the configuration. |
| RUNCFG-CONTEXT | manufacturer-doc | S1 p9 | show running-configuration context interface <name> prints the version comment line and that interface's block. |
| INTERFACE-NAMES | manufacturer-doc | S1 p5-8; S2 p29 | Interfaces are named gigabitethernetN, tengigabitethernetN, loopbackN, vlanN and downstreamN, all lower case, number attached. |
| INTERFACE-NO-SHUTDOWN | manufacturer-doc | S1 p5-8 | An enabled interface carries 'no shutdown'. How a disabled one is written is not shown. |
| STANZA-SYNTAX | manufacturer-doc | S1 p5-9 | Seen verbatim: hostname <name>; ip address <ip> <mask>; description <text>; vlan member <id>; vlan untagged <id>; port type uni|nni vlan <id>; port uplink; ip access-group <name> in; ip strict-clients; arp proxy; ip dhcp relay script; ip dhcp snoop information-tag policy drop; ip dhcp auto-policy-map snoop vlan <id>; access-list <name> with ' seq <n> permit|deny ...'; router ospf; service-definition; service-selection; parameter dhcp ... |
| SHOW-VERSION-MS4K-630 | manufacturer-doc | S2 p26 | show version on an MS4026-AC with iBOS 6.3.0-ED-R: product line, copyright, routing engine, compiled, source id, '<hostname> uptime is <n>', last boot, system image file and version, System, bootloader version, PCBA revision, product id, serial number/base MAC address, processor, RAM. |
| SHOW-VLAN | manufacturer-doc | S2 p29 | show vlan prints a table VLAN / Interfaces with the interface names wrapped three to a line. |
| SHOW-IP-INTERFACE-BRIEF | manufacturer-doc | S1 p6 | show ip interface brief (sh ip int br) prints Interface, IP-Address, Netmask, SNPA, Protocol; an asterisk before the address marks it as added at run time. |
| SHOW-CLIENTS | manufacturer-doc | S1 p9 | show clients lists snooped DHCP clients: Address, SNPA, Lease, Type, Interface. |
| SHOW-PFDP-NEIGHBOURS | manufacturer-doc | S2 p27 | show pfdp neighbours lists the neighbouring Waystream/PacketFront devices per interface with their image, model, remote interface and activity. |
| SECRET-SYNTAX-SNMP-RADIUS | third-party-driver | S3 | Secrets Oxidized masks: ' community <string> ...' and ' notify <ip> community <string> ...' inside 'snmp-group version 2c', and 'radius server <ip> secret <string> ...'. |

## INFERRED (9)

| Id | Basis | Sources | Statement | Why only inferred | Mock |
|---|---|---|---|---|---|
| LOGIN-LANDING-MODE | third-party-driver | S3; S4 | Some devices land in user mode and need enable before show running-config, others land in privileged mode: Oxidized runs enable only when told to, and the 7.6.2 report is solved by telling it to. | Nothing says which firmware or configuration lands where; the mock offers both. | assumes it |
| ERROR-FORMAT | third-party-report | S4 | An unknown command is answered with a line '%-ERR: <the command line>' and a line with carets under the offending word followed by ' Invalid command'. | One report, one command: 'show running-config' gives carets (14) under 'running-config' starting at column 12. Other errors (ambiguous, incomplete, wrong argument) are not shown anywhere. | assumes it |
| RUNCFG-7X-REJECTED | third-party-report | S4 | On an MS7048-AC with iBOS 7.6.2-GD-R show running-config was answered with an error. The reporter suspected missing enable; a maintainer suggested enabling it. Whether that fixed it is not recorded. | A single stale report. The cause (privilege, firmware, syntax) is open. | assumes it |
| RUNCFG-DOC-INDENT-ARTIFACT | manufacturer-doc | S1 p8 | Several lines of the MS4000 example on page 8 have no indentation (port type, ip access-group, description) and one interface is written 'tengigabitethernet 1' with a space. The same lines are indented on page 9, so this is read as a typesetting artifact, not as device output. | Same firmware and same lines indented on the next page; a parser that depends on indentation should still not break on it. | not simulated |
| RUNCFG-ORDER-MS4K | manufacturer-doc | S1 p8-9 | On MS4000 and 7.x the order of ASR6000 is assumed: interfaces first, then hostname, access-list, and the '!end' marker. The MS4000 example starts at the base configuration and shows no hostname line. | Same operating system family and the same printing code is likely, but no MS4000 example shows the whole output. | assumes it |
| SHOW-VERSION-MS4K-635 | manufacturer-doc | S2 p26; S1 p9 | show version on an MS4000 with iBOS 6.3.5-ED-R has the layout of the 6.3.0-ED-R output. Only the image name in the running-config header proves the 6.3.5 firmware exists. | Same product line, five patch levels apart; no 6.3.5 show version is shown anywhere. | assumes it |
| RUNCFG-MS4K-630 | manufacturer-doc | S2 p26; S1 p9 | show running-config works on an MS4000 with iBOS 6.3.0-ED-R and looks like the 6.3.5 output with an older image name in the header. | The installation guide for 6.3.0 never shows it; the certification document shows it for 6.3.5. | assumes it |
| RUNCFG-7X-AFTER-ENABLE | third-party-report | S4 | On 7.x show running-config is accepted once enable has been given, and then looks like the 6.x output. | The reporter suspected missing enable and a maintainer suggested it; the thread never says whether it helped, and no 7.x running-config is shown. | assumes it |
| SHOW-VERSION-7X | third-party-report | S4 | show version on an MS7048-AC with iBOS 7.6.2-GD-R carries the same lines plus board type/version and two CPLD revisions. The report shows it after Oxidized prefixed every line with '! ', and with the first and last lines cut. | Reconstructed from a pasted, post-processed output. | assumes it |

## UNKNOWN (14)

| Id | Statement | How to find out | Mock |
|---|---|---|---|
| PROMPT-TRAILING-SPACE | Whether the prompt is followed by a space. Oxidized allows one; a prompt that ends in a space once broke a prompt pattern on another vendor. | Capture the raw bytes after the prompt (ssh with a pty and hexdump) on a real switch. | assumes an answer |
| SSH-AUTH-METHODS | Which SSH authentication methods the device offers (password, keyboard-interactive, public key), its host key types, key exchange and cipher lists, and whether it needs a pty. | ssh -vvv to the switch and keep the output of the negotiation; try the transport with default algorithms first. | assumes an answer |
| ENABLE-WRONG-PASSWORD | What the device prints when the enable password is wrong, and whether it limits attempts. | Only with the customer's agreement: one wrong attempt, then read the answer. Do not repeat; accounts may lock. | assumes an answer |
| PAGER-BEHAVIOUR | What the pager prints and how it is dismissed when terminal no pager has not been sent or is rejected. | Run show running-config before terminal no pager on a real switch and keep the raw bytes. | not simulated |
| RUNCFG-BLOCK-SEPARATOR | Whether a real device separates top-level stanzas with a blank line (as the document shows), with '!' or with nothing. The document may have reformatted it. | Look at the raw bytes of a real show running-config between two interfaces. | assumes an answer |
| INTERFACE-DISABLED-FORM | The line a disabled interface shows (shutdown?) and whether defaults are printed. | Shut one lab port on a real switch and read the block. | assumes an answer |
| SHOW-VERSION-ASR6000 | show version output on an ASR6000. No source shows it; only the image name in the running-config header is known. | Capture show version on an ASR6000. | assumes an answer |
| SHOW-LLDP | Whether iBOS has LLDP and how its neighbours are shown; PFDP is the only neighbour protocol seen. | show lldp neighbors / show lldp neighbours on a real switch. | not simulated |
| SECRET-SYNTAX-OTHER | Every other place a secret can appear (local users, enable, TACACS+, SSH or SNMPv3 keys, routing keys, ZTP) is unknown. Oxidized does not mask them either. | Search a real show running-config for password, secret, key, community, md5 and encrypted-looking strings before anything is stored or shared. | assumes an answer |
| CONFIG-MODE-ENTRY | How configuration mode is entered, what its prompt looks like and how it is left. A sibling PacketFront OS (DRGOS) uses 'configure terminal'; that is a hint, not evidence for iBOS. | Read the iBOS Command Reference Guide, then confirm on a lab switch before any write. | assumes an answer |
| CONFIG-SAVE-COMMIT | Whether a change is live at once, how it is saved (write memory? copy running-config startup-config? commit?), whether there is a rollback. | Same as CONFIG-MODE-ENTRY; also test what a reload does to an unsaved change. | assumes an answer |
| CONFIG-ERROR-FEEDBACK | How a rejected configuration line is reported, and whether the rest of a pasted block is still applied. | Send one valid and one invalid line to a lab switch and keep the answer. | assumes an answer |
| LINE-ENDINGS-ANSI | Line endings (CRLF), escape sequences or backspace handling in the output. | Capture a session with script(1) or a debug transport and inspect the bytes. | assumes an answer |
| SESSION-LIMITS | Idle timeout, number of concurrent SSH sessions, rate limits. | Ask the customer; test with two sessions. | not simulated |
