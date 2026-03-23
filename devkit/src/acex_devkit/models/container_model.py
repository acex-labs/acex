from typing import ClassVar


class ContainerModel:
    """
    Mixin for Pydantic models that are used as values in Dict[str, X] container fields.

    Every subclass MUST declare `identity_fields` as a ClassVar[tuple[str, ...]]:
      - Non-empty tuple: fields whose values uniquely identify this object.
        The differ will match objects across desired/observed by these field values,
        ignoring the dict key entirely.
      - Empty tuple `()`: the dict key itself is the identity (key-based matching).
        Use this for singleton-like entries (e.g., "global", "default") where no
        field inside the object acts as a natural identifier.

    Example:
        class NtpServer(ContainerModel, BaseModel):
            identity_fields: ClassVar[tuple[str, ...]] = ("address",)
            address: AttributeValue[str]
            ...

        class SpanningTreeGlobalConfig(ContainerModel, BaseModel):
            identity_fields: ClassVar[tuple[str, ...]] = ()  # key is identity
            mode: Optional[AttributeValue[str]] = None
            ...
    """

    identity_fields: ClassVar[tuple[str, ...]]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        has_identity_fields = any(
            "identity_fields" in c.__dict__
            for c in cls.__mro__
            if c is not ContainerModel
        )
        if not has_identity_fields:
            raise TypeError(
                f"{cls.__name__} must declare 'identity_fields' as a ClassVar. "
                f"Use identity_fields = ('field_name',) to match by field value, "
                f"or identity_fields = () to match by dict key."
            )
