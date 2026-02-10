# ACE-X DevKit

Development kit for building ACE-X drivers and plugins.

## Installation

```bash
pip install acex-devkit
```

## Usage

### Building a Network Element Driver

```python
from acex_devkit.drivers import NetworkElementDriver, TransportBase, RendererBase, ParserBase
from acex_devkit.models import ComposedConfiguration

class MyRenderer(RendererBase):
    def render(self, model: dict) -> str:
        # Implement your rendering logic
        pass

class MyTransport(TransportBase):
    def connect(self) -> None:
        # Implement connection logic
        pass
    
    def send(self, payload: Any) -> None:
        # Implement send logic
        pass
    
    def verify(self) -> bool:
        # Implement verification logic
        return True
    
    def rollback(self) -> None:
        # Implement rollback logic
        pass

class MyParser(ParserBase):
    def parse(self, configuration: str) -> ComposedConfiguration:
        # Implement parsing logic
        pass

class MyDriver(NetworkElementDriver):
    renderer_class = MyRenderer
    transport_class = MyTransport
    parser_class = MyParser
    
    def render(self, configuration: ComposedConfiguration, asset):
        return self.renderer.render(configuration, asset)
    
    def parse(self, configuration: str) -> ComposedConfiguration:
        return self.parser.parse(configuration)
```

## Package Contents

- **models**: Common data models (Asset, LogicalNode, ComposedConfiguration, etc.)
- **drivers**: Base classes for building network element drivers
- **exceptions**: Common exceptions
- **types**: Type aliases and protocols

## License

AGPL-3.0
