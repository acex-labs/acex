---
kind: fixed
title: Several filters of a generated ConfigMap now all have to match
---
The config builder, reconcile and the Config Translator turned a list of filters into a ConfigMap whose filters were combined with OR, although the guide and the release note said that they apply together. They now combine with AND by default, so role core at site hq applies to the core nodes of hq and not to every core node and everything at hq. A new `filter_match` in the three request bodies (`all` by default, or `any`) chooses OR again. ConfigMaps that were generated earlier are not changed.
