---
kind: added
title: Workers can connect to the broker over TLS with a client certificate
audience: admin
---
When the API says the broker is reached with TLS, the worker connects with `amqps://`, sends the broker's host name
(SNI) and checks the certificate against it. The worker's own host provides what the API cannot:
`ACEX_BROKER_TLS_CA_FILE` for a CA bundle (default: the system's trusted roots), and `ACEX_BROKER_TLS_CERT_FILE` with
`ACEX_BROKER_TLS_KEY_FILE` for a client certificate, set together, when the broker or a gateway in front of it requires
one. The files are read again at every reconnect, so a certificate that is renewed on disk is used without restarting
the worker. A worker started with only one of the two files stops with an error that says so.
