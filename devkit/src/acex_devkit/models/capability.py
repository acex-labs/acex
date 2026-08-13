from enum import StrEnum


class TelemetryCapability(StrEnum):
    """Vocabulary of observable telemetry kinds in ACEX."""

    icmp = "icmp"
    mdt = "mdt"
    snmp = "snmp"
    snmp_trap = "snmp_trap"
    syslog_rfc5424 = "syslog_rfc5424"
