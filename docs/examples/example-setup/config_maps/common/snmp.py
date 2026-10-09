from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.acl import Ipv4Acl, Ipv4AclEntry
from acex.configuration.components.system.snmp import (
    SnmpGlobal,
    SnmpServer,
    SnmpCommunity,
    SnmpUser,
    SnmpTrap,
    SnmpGroup,
    SnmpView,
    SnmpViewOid,
)

from config_maps.core.vrfs import vrfs


class ConfigSNMP(ConfigMap):
    def compile(self, context):

        # ACL FOR SNMP
        snmp_rw_acl = Ipv4Acl(name="snmp_rw")
        context.configuration.add(snmp_rw_acl)

        acl_entry_settings = [
            {
                "sequence_id": 100,
                "description": "Catalyst Centers",
                "source_address": "192.168.1.2",
                "action": "permit",
            },
            {
                "sequence_id": 150,
                "description": "Management Networks",
                "source_address": "192.168.123.96/28",
                "action": "permit",
            },
            {
                "sequence_id": 202,
                "description": "mon-server.example.net",
                "source_address": "10.9.128.43",
                "action": "permit",
            },
        ]

        ## ACL entries
        for entry in acl_entry_settings:
            ipv4aclentry = Ipv4AclEntry(
                name=f"entry{entry['sequence_id']}",  # Unique name for the ACL entry, important to avoid conflicts
                description=entry["description"],
                ipv4_acl=snmp_rw_acl,
                action=entry["action"],
                source_address=entry["source_address"],
                sequence_id=entry["sequence_id"],
            )
            context.configuration.add(ipv4aclentry)

        global_snmp = SnmpGlobal(
            name="global_snmp",
            enabled=True,
        )
        context.configuration.add(global_snmp)

        snmp_server1 = SnmpServer(
            name="snmp_server1",
            address="10.116.140.2",
            enabled=True,
            version="v3",
            network_instance=getattr(vrfs, "test", None),
            # To avoid errors in log. Get example VRF if we can for the specified switch. If can't get any data, set as None.
        )
        context.configuration.add(snmp_server1)

        snmp_server2 = SnmpServer(
            name="snmp_server2",
            address="10.123.20.3",
            enabled=True,
            version="v3",
        )
        context.configuration.add(snmp_server2)

        # snmp_user1 = SnmpUser(
        #    name="snmp_user1",
        #    group=snmp_group_snmpread,
        #    username="snmpread",
        #    security_level="AUTH_NO_PRIV",
        #    auth_protocol="SHA",
        #    auth_password="very_secure_password"
        # )
        # context.configuration.add(snmp_user1)

        snmp_group_snmpread = SnmpGroup(
            name="snmpread",
            access="READ_ONLY",
        )
        context.configuration.add(snmp_group_snmpread)

        snmp_view1 = SnmpView(name="SNMPcommon", group=snmp_group_snmpread)
        context.configuration.add(snmp_view1)

        snmp_oids = [
            {"name": "oid1", "oid": "iso", "included": True},
            {"name": "oid2", "oid": "mib-2", "included": True},
            {"name": "oid3", "oid": "snmpUsmMIB", "included": False},
            {"name": "oid4", "oid": "snmpVacmMIB", "included": False},
            {"name": "oid5", "oid": "snmpCommunityMIB", "included": False},
            {
                "name": "oid6",
                "oid": "cafSessionMethodsInfoEntry.2.1.111",
                "included": False,
            },
        ]

        for oid in snmp_oids:
            snmp_oid_view1 = SnmpViewOid(
                name=oid["name"],
                oid=oid["oid"],
                included=oid["included"],
                view=snmp_view1,
            )
            context.configuration.add(snmp_oid_view1)

        snmp_group_snmonetw = SnmpGroup(
            name="snmonetw", access="READ_WRITE", ipv4acl=snmp_rw_acl
        )
        context.configuration.add(snmp_group_snmonetw)

        snmp_view2 = SnmpView(name="SNMPnetwork", group=snmp_group_snmonetw)
        context.configuration.add(snmp_view2)

        snmp_oids = [
            {"name": "oid1", "oid": "iso", "included": True},
        ]

        for oid in snmp_oids:
            snmp_oid_view2 = SnmpViewOid(
                name=oid["name"],
                oid=oid["oid"],
                included=oid["included"],
                view=snmp_view2,
            )
            context.configuration.add(snmp_oid_view2)

        user1 = SnmpUser(
            name="svccommonnetw",
            group=snmp_group_snmpread,
            username="svccommonnetw",
            security_level="AUTH_NO_PRIV",
            auth_protocol="SHA",
            auth_password="",
        )
        context.configuration.add(user1)

        user2 = SnmpUser(
            name="svccommonnetwpriv",
            group=snmp_group_snmpread,
            username="svccommonnetwpriv",
            security_level="AUTH_NO_PRIV",
            auth_protocol="SHA",
            auth_password="",
        )
        context.configuration.add(user2)


config = ConfigSNMP()
config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
