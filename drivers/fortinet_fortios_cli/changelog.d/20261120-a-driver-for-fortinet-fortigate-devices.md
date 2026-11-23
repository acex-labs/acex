---
kind: added
title: A driver for Fortinet FortiGate devices (first step)
---

ACEX can now reach a FortiGate over SSH and read its configuration with `show full-configuration`. Of that configuration it understands the hostname so far, and every other line is listed as one ACEX has no field for yet, so a node shows how much of the device is covered. Secrets in the configuration, passwords, pre-shared keys and private keys, are masked before it is stored. Writing configuration to a FortiGate and comparing it is not available yet: a change that ACEX would have made is reported as not rendered.
