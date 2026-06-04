
from acex_client.acex.acex import Acex


a = Acex(baseurl = "http://127.0.0.1/")
# a = Acex(baseurl = "https://api.auto.ngninfra.net/", verify=False)


node = a.node_instances.get("5")


print(node)
