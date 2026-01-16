
from acex_client.models.models import LogicalNode, Ned


class LogicalNodes:

    def __init__(
        self,
        rest_client
        ):
        self.rest = rest_client


    def get_all(self):
        response = []
        ep = "/inventory/logical_nodes/"
        api_response = self.rest.query_items(ep)

        for ln in api_response:
            response.append(LogicalNode(**ln))

        return response