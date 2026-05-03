from enum import Enum


class TelemetryCapability(str, Enum):
    """
    Vocabulary of observable telemetry kinds in ACEX.

    Components declare which capability they belong to (e.g. IcmpPingTelemetry
    has `capability = TelemetryCapability.icmp`). TelemetryAgents grant
    capabilities, which gates which components their telegraf config will
    include.
    """

    icmp = "icmp"
    mdt = "mdt"
    snmp = "snmp"
    snmp_trap = "snmp_trap"
    syslog_rfc5424 = "syslog_rfc5424"
