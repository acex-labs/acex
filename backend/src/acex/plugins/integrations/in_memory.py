
from .integration_plugin_base import IntegrationPluginBase

class DatasourceInMemory(IntegrationPluginBase): 

    def __init__(self):
        self.db = {}

    def create(self, item: dict): 
        _id = str(len(self.db)+1)
        item = dict(item)
        item["id"] = _id
        self.db[str(len(self.db)+1)] = item
        return True

    def get(self, id: str): 
        return self.db.get(id)

    def query(self): 
        items = []
        for k, v in self.db.items():
            items.append(v)
        return items

    def update(self,id: str, data: dict ): 
        for k, v in data.items():
            self.db[id][k] = v

    def delete(self, id: str): 
        self.db.pop(id)