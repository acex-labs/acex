---
kind: added
title: Cisco Business firmware is a known platform
---

New `OS.cisco_business` for the firmware of the Catalyst 1300, CBS250 and CBS350, with a version scheme (`CiscoBusinessVersions`) that accepts what it reports: four numbers, for example `4.1.7.17` or `3.5.2.8`. `cisco_ios` and `cisco_iosxe` still take three, so a four-number version on one of them is refused. Five Catalyst 1300 models are declared with the ports of their data sheet (`C1300-8P-E-2G`, `C1300-24P-4X`, `C1300-48P-4X`, `C1300-48P-4G` and `C1300-48T-4G`), so an asset of vendor Cisco, OS `cisco_business` can be created and is offered in the asset form. There is no driver yet.
