---
kind: added
audience: admin
title: A git repository can belong to one site, so its ConfigMaps only reach that site
---
A git repository has a new optional `site`. The ConfigMaps loaded from it then apply only to the logical nodes of that site, on top of their own filters, so a customer can work from one repository for each site and no repository can change another site's devices. A repository without a site works as before. Set it with `site` when adding a repository or in an update, and send `null` to take the limit away; changing it loads the repository again. The match is the exact site name of the logical node. Needs a database migration (one nullable column).
