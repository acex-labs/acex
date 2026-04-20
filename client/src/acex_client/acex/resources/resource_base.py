class PaginatedResult:
    """Wraps a paginated API response with iteration support."""

    def __init__(self, items, total, limit, offset):
        self.items = items
        self.total = total
        self.limit = limit
        self.offset = offset

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __bool__(self):
        return len(self.items) > 0


class Resource:

    def __init__(self, rest_client):
        self.rest = rest_client

    @property
    def ep(self):
        return self.__class__.ENDPOINT or ""

    @property
    def list_model(self):
        return self.__class__.RESPONSE_MODEL_LIST

    @property
    def single_model(self):
        return self.__class__.RESPONSE_MODEL_SINGLE

    def get(self, id):
        data = self.rest.get_item(self.ep, id)
        if data != {}:
            return self.single_model(**data)

    def query(self, limit=100, offset=0, **filters):
        """Query with pagination and filters. Returns PaginatedResult."""
        params = {k: v for k, v in filters.items() if v is not None}
        params["limit"] = limit
        params["offset"] = offset
        data = self.rest.query_items(self.ep, params=params)

        # Handle paginated response: {items: [...], total: N, limit: N, offset: N}
        if isinstance(data, dict) and "items" in data:
            items = [self.list_model(**item) for item in data["items"]]
            return PaginatedResult(items, data["total"], data["limit"], data["offset"])

        # Handle plain list response (e.g. NEDs endpoint)
        if isinstance(data, list):
            items = [self.list_model(**item) for item in data]
            return PaginatedResult(items, len(items), len(items), 0)

        return PaginatedResult([], 0, limit, offset)

    def get_all(self):
        """Backwards-compatible: returns list of all items."""
        return self.query().items
