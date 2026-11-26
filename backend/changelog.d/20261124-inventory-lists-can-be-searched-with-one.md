---
kind: added
title: Inventory lists can be searched with one text, q
---
The lists of node instances, logical nodes, sites, regions and contacts take a `q` parameter, as the lists of assets and of software compliance already did. One text is looked for in several fields at once, whatever its case, and a row is listed when any of them contains it:

- Node instances (`GET /api/v1/inventory/node_instances?q=`): hostname, site and role of the logical node, management IP, and the serial number, hardware model and vendor of the asset.
- Logical nodes (`/inventory/logical_nodes?q=`): hostname, site and role.
- Sites (`/inventory/sites?q=`): name, display name, city, country and address.
- Regions (`/inventory/regions?q=`): name and display name.
- Contacts (`/inventory/contacts?q=`): name, display name, first and family name, email and phone.

A text made only of digits also finds the node instance or logical node with that id. A typed `%` or `_` is that character, not a wildcard. `q` narrows the list together with every other filter, `region` included, and the `total` of the page counts the rows it matches.

`q` on assets now also looks in the operating system and its version. The filters that name one field (`hostname`, `site`, `city` and the rest) work as before.
