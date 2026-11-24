---
kind: fixed
title: A FortiGate is read without changing it, and a partial read is an error
---
The driver used to turn off the pager of the FortiGate's console before it read a command, and turn it back on after. That is a change of the device, it needs write access to the system area, and on a unit with VDOMs it does nothing at the top level, so the read stopped at the first page: the serial number was missing and the configuration ended halfway, without any error. The driver now answers the pager's `--More--` with a key for every page and changes nothing, so the configuration it reads is the device's own (it no longer shows `set output standard` under the console settings).

A configuration that is not whole is an error and is never stored: it must begin with its header, end with its last closing line, hold no pager marker, and on a unit with VDOMs include the global part. Use an administrator that sees all VDOMs for such a unit; an account limited to one VDOM now fails with a message that says so. Checked on a FortiGate-VM 7.6.8 with one VDOM and with VDOMs enabled, as the global administrator. An administrator profile with read access only has not been tried on a real unit.
