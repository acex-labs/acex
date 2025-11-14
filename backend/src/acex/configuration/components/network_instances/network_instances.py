
from acex.configuration.components.base_component import ConfigComponent
from acex.models.network_instances import (
    NetworkInstanceAttributes,
    VlanAttributes,
    L2DomainAttributes,
    VlanMapAttributes
)

from pydantic import BaseModel

class NetworkInstance(ConfigComponent): ...


class L2Vlan(ConfigComponent): 
    type = "l2vlan"
    model_cls = VlanAttributes

class VlanMap(ConfigComponent):
    type = "vlan_map"
    model_cls = VlanMapAttributes
    vlans: dict[str, L2Vlan]

    def to_json(self):
        return {key: vlan.to_json() for key, vlan in self.children.get('vlans').items()}

class L2Domain(NetworkInstance):
    type = "l2vsi"
    model_cls = L2DomainAttributes
    vlans: VlanMap

    def pre_init(self, kwargs: dict):
        """Handle vlans parameter conversion to VlanMap"""
        vlans_input = kwargs.get('vlans')
        
        if vlans_input is None:
            # Case 3: No vlan referenced - use empty VlanMap
            kwargs['vlans'] = VlanMap(vlans={})
        elif isinstance(vlans_input, L2Vlan):
            # Case 1: Single vlan mapped - use VlanMap with single vlan
            vlan_key = vlans_input._key if hasattr(vlans_input, '_key') else 'vlan'
            kwargs['vlans'] = VlanMap(vlans={vlan_key: vlans_input})
        elif isinstance(vlans_input, list):
            # Case 2: List of vlans - use VlanMap with all listed vlan instances
            vlan_dict = {}
            for vlan in vlans_input:
                if isinstance(vlan, L2Vlan):
                    vlan_key = vlan._key if hasattr(vlan, '_key') else f'vlan_{len(vlan_dict)}'
                    vlan_dict[vlan_key] = vlan
            kwargs['vlans'] = VlanMap(vlans=vlan_dict)
        elif isinstance(vlans_input, VlanMap):
            # Already a VlanMap, use as-is
            pass
        else:
            # Invalid type, use empty VlanMap
            kwargs['vlans'] = VlanMap(vlans={})
        



class Vlan(NetworkInstance):
    """
    Composite config component combining L2Vlan and L2Domain.
    Creates both a VLAN and its associated L2 domain instance.
    """
    type = "l2vsi"
    model_cls = NetworkInstanceAttributes
    
    def pre_init(self, kwargs: dict):
        vlan_id =  kwargs.pop("vlan_id")
        name = kwargs.pop("vlan_name")
        kwargs["bajs"] = "korv"
        # Create the L2Vlan instance, auto create a 1:1 map
        vlan_instance = L2Vlan(name=name, vlan_id=vlan_id)
        vlan_map = VlanMap(
            name=f"vlan_map_{name}",
            vlans={name: vlan_instance}
        )
        self.children["vlans"] = vlan_map

        return None
