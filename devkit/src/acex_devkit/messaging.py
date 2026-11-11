"""What every AMQP client of ACEX needs to speak TLS to the broker."""

from __future__ import annotations

import ssl
from typing import Any


def amqp_ssl_options(
    *,
    tls: bool,
    ca_file: str | None = None,
    cert_file: str | None = None,
    key_file: str | None = None,
) -> dict[str, Any] | None:
    """The options for Celery's ``broker_use_ssl``, or None when TLS is off.

    The broker's certificate is always verified: against ``ca_file`` when one is given, else against the system's
    trusted roots. A client certificate is presented only when ``cert_file`` is given, for brokers (or a gateway in
    front of them) that require one; its files are read each time a connection is opened, so a certificate that is
    renewed on disk is used from the next reconnect.

    ``server_hostname`` is None on purpose. It is a marker that kombu replaces with the host of the broker URL. That is
    what makes the client send SNI and check the certificate against the host name. Without the key py-amqp does
    neither, which would not reach a broker behind a gateway that routes by SNI, and would accept a certificate for any
    other name.
    """
    if not tls:
        return None
    if (cert_file is None) != (key_file is None):
        raise ValueError("A client certificate needs both the certificate file and the key file.")
    options: dict[str, Any] = {"cert_reqs": ssl.CERT_REQUIRED, "server_hostname": None}
    if ca_file:
        options["ca_certs"] = ca_file
    if cert_file and key_file:
        options["certfile"] = cert_file
        options["keyfile"] = key_file
    return options
