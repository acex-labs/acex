# resolver.py
import yaml as pyyaml
import os
from typing import Dict, Any

test_path = os.path.abspath(os.getcwd())

#def resolve_device_spec(hardware_model: str) -> Dict[str, Any]:
#    hardware_model = hardware_model.lower()
#    with open(test_path + f"/models/{hardware_model}.yaml") as f:
#        device_data = pyyaml.safe_load(f)
#    return device_data
#
#def resolve_hardware_model_data():
#    data = resolve_device_spec("C9300L-24P-4X")
#    
#    for intf_type, intf_data in data.get("interfaces", {}).items():
#        max_index = intf_data.get("max_index")
#        speed = intf_data.get("speed")
#        print(f"Interface type: {intf_type}, Max index: {max_index}, Speed: {speed}")
        
def parse_model(hardware_model: str, model_dir: str) -> Dict[str, Any]:
    hardware_model = hardware_model.lower()
    # Default path is:
    # acex/drivers/cisco_ios_cli/src/acex_driver_cisco_ioscli/device_types/models
    with open(os.path.join(model_dir, f"{hardware_model}.yaml")) as f:
        device_data = pyyaml.safe_load(f)
    return device_data

def test():
    model_dir = os.path.join(test_path, "models")
    #data = parse_model("C9300L-24P-4X", model_dir)
    data = parse_model("johan_test", model_dir)
    
    #for key, value in data.items():
    #    #max_index = intf_data.get("max_index")
    #    #speed = intf_data.get("speed")
    #    print("key:", key)
    #    print("value:", value)
    #for x in data.get("interfaces", {}):
    #for x, y in data.items():
    #    print(x)
    #    print(y)
    #    print('#'*50)
    print('interfaces :', data.get("interfaces", {}))
    print('\n')
    print('prefix_map :', data.get("prefix_map", {}))
    print('speed: ', data.get('prefix_map').get(1000000))
        #prefix = x.get("prefix")
        #last_index = x.get("last_index")
        #speed = x.get("speed")
        #print(f"Interface type: {x}\nlast_index: {last_index}\nSpeed: {speed}")
        
if __name__ == "__main__":
    test()