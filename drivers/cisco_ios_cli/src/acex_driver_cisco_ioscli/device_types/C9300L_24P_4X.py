class DeviceModel:
    def __init__(self):
        self.model = "C9300L-24P-4X"
        
    def interfaces(self):
        full_data = {}
        gig_ether = {
            "max_index": 24,
            "stack_index": 0,
            "module_index": 0,
            "speed": 1000000,
        }
        tengig_ether = {
            "max_index": 4,
            "stack_index": 0,
            "module_index": 0,
            "speed": 10000000,
        }
        full_data["GigabitEthernet"] = gig_ether
        full_data["TenGigabitEthernet"] = tengig_ether
        return full_data