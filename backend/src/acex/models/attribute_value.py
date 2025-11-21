from pydantic import BaseModel, field_validator, model_validator, field_serializer
from typing import Union, TypeVar, Generic, Optional, Dict, Any, get_args, get_origin
from acex.models.external_value import ExternalValue

T = TypeVar('T')

class AttributeValue(BaseModel, Generic[T]):
    """
    A value that can be either a static value of type T or an ExternalValue reference.
    
    Examples:
        # Static string value
        hostname = AttributeValue[str](value="router-01")
        
        # External value reference
        hostname = AttributeValue[str](value=ExternalValue(...))
        
        # With metadata
        hostname = AttributeValue[str](value="router-01", metadata={"source": "cmdb", "priority": 100})
    """
    value: Union[T, ExternalValue]
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator('value', mode='before')
    @classmethod
    def validate_value(cls, v):
        # If it's already an ExternalValue or the expected type, return it
        if isinstance(v, ExternalValue):
            return v
        # Handle dict that should be ExternalValue
        if isinstance(v, dict) and 'ref' in v:
            return ExternalValue(**v)
        return v
    
    @model_validator(mode='after')
    def set_automatic_metadata(self):
        """Automatically set metadata based on value type."""
        if self.metadata is None:
            self.metadata = {}
        
        # Set value_type: concrete or external
        if isinstance(self.value, ExternalValue):
            self.metadata['value_type'] = 'external'
            self.metadata['ref'] = self.value.ref
            self.metadata['plugin'] = self.value.plugin
            self.metadata['ev_type'] = self.value.ev_type.value if hasattr(self.value.ev_type, 'value') else self.value.ev_type
            self.metadata['query'] = self.value.query
            self.metadata['resolved'] = self.value.resolved
            if self.value.kind:
                self.metadata['kind'] = self.value.kind
            # Only include resolved_at if actually resolved
            if self.value.resolved and self.value.resolved_at:
                self.metadata['resolved_at'] = self.value.resolved_at.isoformat() if hasattr(self.value.resolved_at, 'isoformat') else str(self.value.resolved_at)
        else:
            self.metadata['value_type'] = 'concrete'
            # Set the actual type of the value
            self.metadata['type'] = type(self.value).__name__
            
        return self
    
    @field_serializer('value')
    def serialize_value(self, value: Union[T, ExternalValue]):
        """Serialize value - if ExternalValue, return its value, otherwise return as-is."""
        if isinstance(value, ExternalValue):
            return value.value
        return value
    
    def is_external(self) -> bool:
        """Check if this is an external value reference."""
        return isinstance(self.value, ExternalValue)
    
    def get_value(self) -> T:
        """Get the actual value (resolves ExternalValue if needed)."""
        if isinstance(self.value, ExternalValue):
            # TODO: Resolve external value
            return self.value.value
        return self.value
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set a metadata field."""
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a metadata field."""
        if self.metadata is None:
            return default
        return self.metadata.get(key, default)
