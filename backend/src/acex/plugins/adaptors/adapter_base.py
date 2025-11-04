


class AdapterBase:

    VALID_CAPABILITIES = [
        "create",
        "get",
        "query",
        "update",
        "delete"
    ]

    def __init__(self, plugin):
        self.plugin = plugin

    def http_verb(self, capability):
        return {
            "create": "POST",
            "get": "GET",
            "query": "GET",
            "update": "PATCH",
            "delete": "DELETE"
        }.get(capability)

    def path(self, capability):
        return {
            "create": "/",
            "get": "/{id}",
            "query": "/",
            "update": "/{id}",
            "delete": "/{id}"
        }.get(capability)

    @property
    def capabilities(self):
        caps = []
        for cap in self.__class__.VALID_CAPABILITIES:
            if hasattr(self.plugin, cap):
                caps.append(cap)
        return sorted(caps)
