
from acex.configuration.components.base_component import ConfigComponent
from acex.models.network_instances import NetworkInstanceAttributes, VlanAttributes, L2DomainAttributes, L2DomainL2VlanCompositionAttributes

from pydantic import BaseModel

class NetworkInstance(ConfigComponent): ...


class L2Vlan(ConfigComponent): 
    type = "l2vlan"
    model_cls = VlanAttributes

class VlanMap(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    vlans: dict[str, L2Vlan]

    def to_json(self):
        return {key: vlan.to_json() for key, vlan in self.vlans.items()}

class L2Domain(NetworkInstance):
    type = "l2vsi"
    model_cls = L2DomainAttributes
    vlans: VlanMap

    def pre_init(self, *args, **kwargs) -> dict:
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
        
        return kwargs



class Vlan(L2Domain):
    """
    Composite config component combining L2Vlan and L2Domain.
    Creates both a VLAN and its associated L2 domain instance.
    """
    type = "Vlan"
    model_cls = L2DomainL2VlanCompositionAttributes
    
    def pre_init(self, *args, **kwargs):

        name = kwargs['name']
        vlan_name = kwargs.get('vlan_name')  # Optional
        vlan_id = kwargs.get('vlan_id')
        
        # Create the L2Vlan instance
        vlan_instance = L2Vlan(name=name, vlan_id=vlan_id)
        
        # Create the L2Domain instance with the vlan reference
        l2domain_instance = L2Domain(
            name=f"{name}_l2vsi",
            vlans=vlan_instance
        )
        

        # Det här verkar inte komma över till instansen i config... ??? 
        kwargs["name"] = "hejsansvejsan"
        kwargs["vlans"] = vlan_instance