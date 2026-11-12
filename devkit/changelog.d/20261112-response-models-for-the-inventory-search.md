---
kind: added
title: Response models for the inventory search
audience: developer
---
`SearchResponse` holds one `SearchGroup` per kind of object with a match (`SearchHitType`), each with its `total` and its best `SearchHit`s: id, label, sublabel and the field and value the text was found in.
