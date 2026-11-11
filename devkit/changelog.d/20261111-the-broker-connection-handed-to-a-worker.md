---
kind: added
title: The broker connection handed to a worker says whether to use TLS
audience: developer
---
`BrokerConnection`, the broker part of `WorkerConnection`, has a new field `tls` (default `False`). A client that does
not know the field keeps connecting without TLS. `acex_devkit.messaging.amqp_ssl_options` builds the Celery
`broker_use_ssl` options for a TLS connection: the broker's certificate is always verified, the host name is sent as
SNI and checked, and a client certificate is presented when its files are given.
