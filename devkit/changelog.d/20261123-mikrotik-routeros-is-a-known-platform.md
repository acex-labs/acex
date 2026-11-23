---
kind: added
title: MikroTik RouterOS is a known platform
---
New `Vendor.mikrotik` and `OS.mikrotik_routeros`, with a version scheme (`MikrotikRouterosVersions`) that accepts what RouterOS reports, for example `6.49.17`, `7.16.1` and `7.17`, and the testing channel spellings `7.17beta2` and `7.17rc3`. The channel that `/system resource print` writes after the number, such as `(stable)`, is not part of the version. Versions compare by their numbers; a pre-release sorts after its release. Six RouterBOARDs are declared, so MikroTik is offered as a vendor when an asset is created: `RB750Gr3` (hEX), `RB760iGS` (hEX S), `RB4011iGS+RM`, `RB5009UG+S+IN`, `CCR2004-16G-2S+` and `CRS326-24G-2S+RM`. Their ports come from MikroTik's product pages, not from an observed device. There is no MikroTik driver yet, so no model is supported by a NED.
