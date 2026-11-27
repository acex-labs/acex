---
kind: added
title: The running config as an action every driver that reads its config has
audience: developer
---
`get_running_config` reads a node's configuration from the device now and
returns it as the device writes it, masked by the driver's codec. It is built
into `Session` rather than written per driver: any driver whose transport
implements `get_config` and that has a codec lists it among its actions.
`Session` now takes the driver's codec, and `Session.BUILT_IN` names the
actions it runs itself.
