---
kind: added
title: Driver syntax numbers keyless lines and reads several spellings of a flag
audience: developer
refs: #380
---
A block whose lines carry their key can leave the key optional in the line pattern, `[{sequence_id:int} ]permit ...`, and name the key of a line that leaves it out by overriding `Block.default_key`. Without the override such a line is still unmatched. A `Flag` can take a tuple for `on` or `off`: the first spelling is written and all of them are read.
