
from acex_client.acex.acex import Acex

a = Acex(baseurl = "http://127.0.0.1/", verify=False)

ni = a.node_instances.get(1)

ned = a.neds.get_driver_instance(ni.asset.ned_id)
rendered_config = ned.render(ni.logical_node, ni.asset)


parsed_config = ned.parse(rendered_config)

print(parsed_config)