"""The shape of ComposedConfiguration, for choosing a path into it."""

from types import NoneType, UnionType
from typing import Literal, Union, get_args, get_origin

from pydantic import BaseModel

from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.augment import AugmentAttributes
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.reference import Reference


class ConfigTreeNode(BaseModel):
    """A field of the configuration tree.

    - branch: holds other fields only, e.g. `system`
    - component: holds attributes of its own, e.g. `system.config`
    - collection: components keyed by name, e.g. `interfaces`; `children` are the fields of each entry
    - attribute: a value of the component holding it, e.g. `hostname`
    """

    name: str
    kind: Literal["branch", "component", "collection", "attribute"]
    #: The model a branch, component or collection entry is, e.g. "NtpServer".
    type: str | None = None
    children: list["ConfigTreeNode"] = []


class ConfigTree:
    """Walks the models of ComposedConfiguration into a tree of `ConfigTreeNode`s."""

    def root(self) -> ConfigTreeNode:
        return self.model("", [ComposedConfiguration], ())

    def field(self, name: str, annotation, seen: tuple) -> ConfigTreeNode:
        types = self.options(annotation)
        if get_origin(annotation) is dict or any(get_origin(t) is dict for t in types):
            values = [v for t in types if get_origin(t) is dict for v in self.options(get_args(t)[1])]
            models = [v for v in values if self.is_model(v)]
            if models:
                entry = self.model(name, models, seen)
                return entry.model_copy(update={"kind": "collection"})
            return ConfigTreeNode(name=name, kind="attribute")
        models = [t for t in types if self.is_model(t)]
        return self.model(name, models, seen) if models else ConfigTreeNode(name=name, kind="attribute")

    def model(self, name: str, models: list[type[BaseModel]], seen: tuple) -> ConfigTreeNode:
        """One node for one model, or for the union of several (an interface is one of a few types)."""
        fields: dict[str, object] = {}
        for model in models:
            for field_name, info in model.model_fields.items():
                fields.setdefault(field_name, info.annotation)
        children = [
            self.field(field_name, annotation, (*seen, *models))
            for field_name, annotation in fields.items()
            if not any(m in seen for m in models)
        ]
        own = any(child.kind == "attribute" for child in children)
        return ConfigTreeNode(
            name=name,
            kind="component" if own else "branch",
            type=" | ".join(m.__name__ for m in models),
            children=children,
        )

    @staticmethod
    def options(annotation) -> list:
        """The types an annotation allows, None left out: `X | None` is X, a union its members."""
        if get_origin(annotation) in (Union, UnionType):
            return [t for t in get_args(annotation) if t is not NoneType]
        return [annotation]

    @staticmethod
    def is_model(annotation) -> bool:
        """A model holding fields, as opposed to a value: AttributeValues, references and augments are values."""
        return (
            isinstance(annotation, type)
            and issubclass(annotation, BaseModel)
            and not issubclass(annotation, AttributeValue | Reference | AugmentAttributes)
        )
