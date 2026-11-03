---
kind: changed
title: The Junos driver lists the changes it can't render in a patch
audience: developer
---
`render_patch` returns a `RenderResult`: the commands as its payload, and in `metadata.unrendered` the paths of the changes no generator handles, which were left out before without a trace. Patch runs don't reach Junos devices yet, since the driver can't parse their configuration.
