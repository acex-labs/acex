import inspect
from acex.models import LogicalNode


class LogicalNodeService:
    """Service layer för LogicalNode business logic inklusive kompilering."""
    
    def __init__(self, adapter, config_compiler, integrations):
        self.adapter = adapter
        self.config_compiler = config_compiler
        self.integrations = integrations
    
    async def _call_method(self, method, *args, **kwargs):
        """Helper för att hantera både sync och async metoder."""
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        else:
            return method(*args, **kwargs)
    
    async def _apply_compilation(self, logical_node, resolve:bool = False):
        """Helper för att applicera kompilering sync eller async."""
        if self.config_compiler and logical_node:
            if inspect.iscoroutinefunction(self.config_compiler.compile):
                return await self.config_compiler.compile(logical_node, self.integrations, resolve)
            else:
                return self.config_compiler.compile(logical_node, self.integrations, resolve)
        return logical_node
    
    async def create(self, logical_node: LogicalNode):
        result = await self._call_method(self.adapter.create, logical_node)
        return result
    
    async def get(self, id: str, resolve: bool = False):

        # Fetch LN from plugin:
        ln = await self._call_method(self.adapter.get, id)

        # Compile
        ln = await self._apply_compilation(ln, resolve=resolve)
        return ln
    
    async def query(self):
        result = await self._call_method(self.adapter.query)
        return result
    
    async def update(self, id: str, logical_node: LogicalNode):
        result = await self._call_method(self.adapter.update, id, logical_node)
        return result
    
    async def delete(self, id: str):
        result = await self._call_method(self.adapter.delete, id)
        return result
    
    @property
    def capabilities(self):
        return self.adapter.capabilities
    
    def path(self, capability):
        return self.adapter.path(capability)
    
    def http_verb(self, capability):
        return self.adapter.http_verb(capability)
