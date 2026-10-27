---
kind: fixed
title: Discovery of a bare device reads the real model, serial and software version
refs: #317, #318
---
Discovery now logs in to the device over SSH with the given credentials and runs `show version`, instead of returning the same fixed model, serial number and software version for every device. The model, serial number and software version are taken from that output; a value the device does not report is returned empty. The operating system is still always reported as `cisco_iosxe`, and the vendor as `cisco`.
