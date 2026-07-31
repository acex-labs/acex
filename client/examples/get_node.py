
from acex_client.acex.acex import Acex



a = Acex(
    baseurl = "http://127.0.0.1:8080/",
    verify=False
)


print(a.node_instances.get("1"))


