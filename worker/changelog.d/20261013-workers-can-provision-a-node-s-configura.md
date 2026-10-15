---
kind: added
title: Workers can provision a node's configuration over ZTP
audience: admin
refs: #314
---
The new job type `acex.ztp.provision` sends the node's logical-node configuration to the device through its primary management connection, using the NED of the node's asset and the method's bootstrap login, then sets the node's provision status to provisioned. The job fails if the node has no primary management connection with an IP address.
