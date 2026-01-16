
from acex_client.models.models import Node,NodeResponse, Ned


class NodeInstances:

    def __init__(
        self,
        rest_client
        ):
        self.rest = rest_client


    def get_all(self):
        response = []
        ep = "/inventory/node_instances/"
        api_response = self.rest.query_items(ep)

        for ln in api_response:
            response.append(LogicalNode(**ln))

        return response

    def get(self, id):
        ep = f"/inventory/node_instances/"
        api_response = self.rest.get_item(ep, id)
        return Node(**api_response)
