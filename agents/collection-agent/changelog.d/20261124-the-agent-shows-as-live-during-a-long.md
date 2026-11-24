---
kind: fixed
title: The agent shows as live during a long collection round
---

The web interface calls an agent offline when its last acknowledgement is more than two minutes old, and the agent only acknowledged between collection rounds. A round over a couple of thousand nodes takes several minutes, so the agent looked offline for part of every round although nothing was wrong. It now acknowledges the manifest every minute while a round runs, from a thread of its own, so a busy round cannot hold the acknowledgement back.
