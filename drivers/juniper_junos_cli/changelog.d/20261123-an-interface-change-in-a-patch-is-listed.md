---
kind: fixed
title: An interface change in a patch is listed as not rendered
---
A patch that changes an interface no longer carries a stand-in line, `set interfaces TODO description "TODO"`, that would have been sent to the device as it was. The change is reported as not rendered and nothing is written for it. A hostname change is rendered as before. Patches do not reach Junos devices yet, because the driver cannot read their configuration, so the line could not be sent.
