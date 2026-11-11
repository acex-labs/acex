"""Tests for the TLS options every AMQP client of ACEX shares, and the worker's broker connection model."""

import ssl

import pytest
from acex_devkit.messaging import amqp_ssl_options
from acex_devkit.models.worker import BrokerConnection


def test_there_are_no_options_without_tls():
    assert amqp_ssl_options(tls=False) is None
    assert amqp_ssl_options(tls=False, ca_file="/tls/ca.crt", cert_file="/tls/tls.crt", key_file="/tls/tls.key") is None


def test_the_broker_is_verified_and_named_with_tls():
    # server_hostname None is the marker kombu replaces with the host of the URL: SNI and a host name check.
    assert amqp_ssl_options(tls=True) == {"cert_reqs": ssl.CERT_REQUIRED, "server_hostname": None}


def test_a_ca_bundle_and_a_client_certificate_are_passed_on():
    options = amqp_ssl_options(tls=True, ca_file="/tls/ca.crt", cert_file="/tls/tls.crt", key_file="/tls/tls.key")

    assert options == {
        "cert_reqs": ssl.CERT_REQUIRED,
        "server_hostname": None,
        "ca_certs": "/tls/ca.crt",
        "certfile": "/tls/tls.crt",
        "keyfile": "/tls/tls.key",
    }


@pytest.mark.parametrize("files", [{"cert_file": "/tls/tls.crt"}, {"key_file": "/tls/tls.key"}])
def test_a_client_certificate_needs_both_files(files):
    with pytest.raises(ValueError, match="both the certificate file and the key file"):
        amqp_ssl_options(tls=True, **files)


def test_a_broker_connection_does_not_use_tls_unless_told_to():
    broker = BrokerConnection.model_validate({"host": "rabbitmq", "port": 5672, "vhost": "/"})

    assert broker.tls is False


def test_a_broker_connection_from_an_older_backend_still_parses():
    # No "tls" in the answer: a worker newer than the backend it asks.
    broker = BrokerConnection.model_validate_json('{"host": "rabbitmq", "port": 5672, "vhost": "/", "user": "acex"}')

    assert broker.tls is False


def test_the_tls_setting_travels_with_the_connection():
    broker = BrokerConnection(host="berget.amqp.example", port=443, vhost="/", tls=True)

    assert broker.model_dump(mode="json")["tls"] is True
