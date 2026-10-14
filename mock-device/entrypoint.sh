#!/bin/sh
set -e

# Patch hostname into snmpd.conf at runtime
HOSTNAME="${MOCK_HOSTNAME:-mock-device}"
OS_VERSION="${MOCK_OS_VERSION:-17.09.04a}"
sed -i "s/^sysDescr.*/sysDescr    Cisco IOS Software, Catalyst Platform, Version $OS_VERSION ($HOSTNAME)/" /etc/snmp/snmpd.conf

# Start SNMP daemon in background
snmpd -f -Lo -c /etc/snmp/snmpd.conf &

# Start SSH server
exec python server.py
