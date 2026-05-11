from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.acl import Ipv4Acl, Ipv4AclEntry
from acex.configuration.components.system.snmp import SnmpGlobal, SnmpServer, SnmpCommunity, SnmpUser, SnmpTrap, SnmpView, SnmpGroup, SnmpViewOid
from acex.configuration.components.network_instances import L3Vrf

class ConfigSNMP(ConfigMap):
    def compile(self, context):

        test_vrf = L3Vrf(
            name="test_vrf",
        )
        context.configuration.add(test_vrf)

        global_snmp = SnmpGlobal(
            name="global_snmp",
            contact="NOC@example.com",
            location="Example city",
        )
        context.configuration.add(global_snmp)

        snmp_server1 = SnmpServer(
            name="snmp_server1",
            address="192.168.123.10",
            enabled=True,
            version="v3",
            #community="asdasdasd",
            network_instance=test_vrf
        )
        context.configuration.add(snmp_server1)

        snmp_server2 = SnmpServer(
            name="snmp_server2",
            address="192.168.123.11",
            enabled=True,
            version="v3",
            #community="asdasdasd",
        )
        context.configuration.add(snmp_server2)
        
        snmp_community = SnmpCommunity(
            name="snmp_community1",
            community_string="asdasdasd",
        )
        context.configuration.add(snmp_community)

class SnmpViewConfig(ConfigMap):
    def compile(self, context):
        # ACL FOR SNMP
        ipv4acl = Ipv4Acl(
            name="snmp_rw"
        )
        context.configuration.add(ipv4acl)

        acl_entry_settings = [
            {
                "sequence_id": 100,
                "description": "Server 1",
                "source_address": "172.16.123.1",
                "action": "permit"
            },
            {
                "sequence_id": 101,
                "description": "Server 2",
                "source_address": "172.16.123.2",
                "action": "permit"
            },
        ]

        # ACL entries
        for entry in acl_entry_settings:
            ipv4aclentry = Ipv4AclEntry(
                name=f"entry{entry['sequence_id']}",
                description=entry["description"],
                ipv4_acl=ipv4acl,
                action=entry["action"],
                source_address=entry["source_address"],
                sequence_id=entry["sequence_id"]
            )
            context.configuration.add(ipv4aclentry)
            
        snmp_group1 = SnmpGroup(
            name="snmp_group1",
            access="READ_ONLY",
            ipv4acl=ipv4acl,
        )
        context.configuration.add(snmp_group1)

        snmp_user1 = SnmpUser(
            name="snmp_user1",
            group=snmp_group1,
            username="snmpread",
            security_level="AUTH_NO_PRIV",
            auth_protocol="SHA",
            auth_password="very_secure_password"
        )
        context.configuration.add(snmp_user1)

        snmp_view1 = SnmpView(
            name="snmp_view1",
            group=snmp_group1
        )
        context.configuration.add(snmp_view1)
        
        snmp_oids = [
            {
                "name": "oid1",
                "oid": "iso",
                "included": True
            },
            {
                "name": "oid2",
                "oid": "mib-2",
                "included": True
            }
        ]
        
        for oid in snmp_oids:
            snmp_oid = SnmpViewOid(
                name=oid["name"],
                oid=oid["oid"],
                included=oid["included"],
                view=snmp_view1
            )
            context.configuration.add(snmp_oid)
            


config = ConfigSNMP()
config.filters = FilterAttribute("site").eq("/.*/")

view_config = SnmpViewConfig()
view_config.filters = FilterAttribute("site").eq("/.*/")