import requests
from models.models import ComposedConfiguration
from datetime import datetime


from acex.acex import Acex

t = requests.get("http://127.0.0.1/api/v1/inventory/logical_nodes/1")
t = t.json()

cc = ComposedConfiguration(**t["configuration"])

# print(cc.system)
