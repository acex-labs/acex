
from acex_client.acex.acex import Acex

a = Acex(baseurl = "https://api.auto.ngninfra.net/", verify=False)

ni = a.node_instances.get(2)

ned = a.neds.get_driver_instance(ni.asset.ned_id)
rendered_config = ned.render(ni.logical_node, ni.asset)

print(rendered_config)