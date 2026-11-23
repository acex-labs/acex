---
kind: fixed
title: A whole region name finds that region only, in lists and when assigning sites
audience: developer
---
A region was found by a pattern, so a region whose name is part of another's got the sites of both: `eu` listed the sites of `eu-north` in `GET /api/v1/inventory/regions/{id}` and in the list of regions with their sites. Where two sites had names like `hq` and `hq-2`, the region could show the details of the wrong one. Both now use the whole name.

Assigning a site to a region (`POST /api/v1/inventory/region_assignments`) had the same flaw in two ways. A site already in `eu-north` was refused with 409 when assigned to `eu`. And a region or a site that does not exist was accepted when a longer name contained it (assigning to `eu` when only `eu-north` existed stored an assignment to a region that is not there). It now answers 409 only for an assignment that exists, and 404 for a region or site that does not.

The `region` filter of the node instance, logical node and site lists did the same: `region=eu` also returned what is in `eu-north`. Now a whole region name, in any case, means that region and no other, even when it has no sites. A part of a name still matches every region that contains it, as before, so `region=eu` finds both `eu-north` and `eu-south` while no region is named `eu`. Creating a region with exactly that name changes what the filter finds.
