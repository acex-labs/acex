#!/bin/sh
set -e

# Patch hostname into snmpd.conf at runtime
HOSTNAME="${MOCK_HOSTNAME:-mock-device}"
sed -i "s/^sysDescr.*/sysDescr    Cisco IOS Software, Catalyst Platform, Version 16.12.4 ($HOSTNAME)/" /etc/snmp/snmpd.conf

# Start SNMP daemon in background
snmpd -f -Lo -c /etc/snmp/snmpd.conf &

# Start SSH server
exec python server.py
