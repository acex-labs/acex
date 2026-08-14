
# NED interface 

## Config

switch:config --> parse --> composedConfig
composedCondig --> render --> switch syntax

configDiffer(config1, config2) -> Diff

render_patch(diff:Diff) -> [commands]


--- 



## Transport

```mermaid
flowchart LR
    A[Box 1] --> B[Box 2]
    B --> C[Box 3]
```


## Parser


## Renderer

mermaid.js 



--- 

### Annat, tankar wip.
- ping ? 
- show route table? 
- arp table? 
- raw pipe console (tar emot valfria kommandon, utan syntax abstraktion)

Example:


```python
class CiscoIOSCLIDriver(NetworkElementDriver):
    """Cisco IOS CLI driver."""

    opetator_class = 
    renderer_class = CiscoIOSCLIRenderer
    transport_class = CiscoIOSTransport
    parser_class = CiscoIOSCLIParser
    normalizer_class = CiscoIOSNormalizer

    def render(self, configuration: ComposedConfiguration, asset):
        return self.renderer.render(configuration, asset)

    def parse(self, configuration: str) -> ComposedConfiguration:
        return self.parser.parse(configuration)

    def render_patch(self, diff: Diff, node_instance: Any):
        return self.renderer.render_patch(diff, node_instance)

    async def apply_patch(
        self, diff: Diff, node_instance, node: NodeListItem, connection: ManagementConnection, **kwargs
    ):
        commands = self.render_patch(diff, node_instance=node_instance)
        commands = [c.lstrip() for c in commands.splitlines() if c.strip() != "!"]
        return await self.transport.send_config(node, connection, commands, **kwargs)
```



