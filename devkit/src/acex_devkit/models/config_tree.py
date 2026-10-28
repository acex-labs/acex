"""The shape of a configuration model, for choosing a path into it."""

from types import NoneType, UnionType
from typing import Literal, Union, get_args, get_origin

from pydantic import BaseModel

from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.augment import AugmentAttributes
from acex_devkit.models.reference import Reference


class ConfigTreeNode(BaseModel):
    """A field of the configuration tree.

    - branch: holds other fields only, e.g. `system`
    - component: holds attributes of its own, e.g. `system.config`
    - collection: components keyed by name or listed, e.g. `interfaces`; `children` are the fields of each entry
    - attribute: a value of the component holding it, e.g. `hostname`
    """

    name: str
    kind: Literal["branch", "component", "collection", "attribute"]
    #: The model a branch, component or collection entry is, e.g. "NtpServer".
    type: str | None = None
    children: list["ConfigTreeNode"] = []


class ConfigTree:
    """The shape of a configuration model: which fields hold components and which are values, and the tree a
    path walks. ConfigDiffer goes by the same rules, so every path the tree offers is one a diff reaches."""

    def __init__(self, root: type[BaseModel]):
        self.root_model = root

    def root(self) -> ConfigTreeNode:
        return self.model("", [self.root_model], ())

    def field(self, name: str, annotation, seen: tuple) -> ConfigTreeNode:
        entries = self.entries(annotation)
        models = [t for t in (self.options(annotation) if entries is None else entries) if self.is_model(t)]
        if not models:
            return ConfigTreeNode(name=name, kind="attribute")
        node = self.model(name, models, seen)
        return node if entries is None else node.model_copy(update={"kind": "collection"})

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
        return ConfigTreeNode(
            name=name,
            kind="component" if any(self.is_component(m) for m in models) else "branch",
            type=" | ".join(m.__name__ for m in models),
            children=children,
        )

    @classmethod
    def is_component(cls, model: type[BaseModel]) -> bool:
        """A model with attributes of its own, the unit a diff compares; one holding only components is a branch."""
        return any(not cls.holds_components(info.annotation) for info in model.model_fields.values())

    @classmethod
    def holds_components(cls, annotation) -> bool:
        """Whether a field holds components rather than a value: a model, or a collection of them."""
        entries = cls.entries(annotation)
        return any(cls.is_model(t) for t in (cls.options(annotation) if entries is None else entries))

    @classmethod
    def entries(cls, annotation) -> list | None:
        """The types a collection's entries may be, a dict's values or a list's items; None for no collection.
        A dict's key is a name only: entries are told apart by their identity, listed or keyed alike."""
        collections = [t for t in cls.options(annotation) if get_origin(t) in (dict, list)]
        if not collections:
            return None
        return [entry for t in collections for entry in cls.options(get_args(t)[-1])]

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
