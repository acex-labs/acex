from typing import Any

from pydantic import model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    SettingsError,
)


def _is_section(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, Section)


class _Unparsable(ValueError):
    pass


class _OwnFieldsEnvSource(EnvSettingsSource):
    """Environment source that leaves nested sections to their own prefix.

    Without it a parent would also accept e.g. ACEX_DB__HOST for DB_HOST, and
    every setting would have two names. It also names the variable, and how
    to write it, when a value cannot be parsed.
    """

    def __call__(self) -> dict[str, Any]:
        try:
            return super().__call__()
        except SettingsError as exc:
            # The base class wraps every parse error in a message that names
            # only the field; surface ours instead.
            if isinstance(exc.__cause__, _Unparsable):
                raise SettingsError(str(exc.__cause__)) from exc.__cause__.__cause__
            raise

    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        if _is_section(field.annotation):
            return None
        try:
            return super().prepare_field_value(field_name, field, value, value_is_complex)
        except ValueError as exc:
            name = f"{self.env_prefix}{field_name}".upper()
            raise _Unparsable(
                f"{name} could not be parsed ({exc}). Give it as JSON, or set its parts "
                f"one by one as {name}__<KEY>__<FIELD> (see acex.settings)."
            ) from exc


class Section(BaseSettings):
    """A group of settings that share an environment prefix.

    Declare a section by subclassing with its prefix; every field is then
    settable both in code and from the environment, with nothing else to write:

        class OidcSettings(Section, env_prefix="OIDC_"):
            #: OIDC provider that issues the bearer tokens the API accepts.
            issuer_url: str | None = None

        OidcSettings(issuer_url="https://...")   # in code
        OIDC_ISSUER_URL=https://...              # in the environment

    A value given in code wins over the environment, which wins over the
    default. Nested models and dicts are reached with "__" between the levels
    (ACEX_AI_PROVIDERS__GROQ__BASE_URL); lists and dicts can also be given as
    JSON. A dict given in both places is merged key by key, code winning per
    key. Empty environment values count as unset. Unknown fields are
    rejected, so a misspelt setting fails loudly instead of being ignored.

    A section can hold other sections. Each keeps its own prefix, and one given
    in code as a dict still reads its missing fields from its own prefix.
    """

    model_config = SettingsConfigDict(
        env_ignore_empty=True,
        env_nested_delimiter="__",
        extra="forbid",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, _OwnFieldsEnvSource(settings_cls), dotenv_settings, file_secret_settings

    @model_validator(mode="before")
    @classmethod
    def _build_subsections(cls, data: Any) -> Any:
        # Validating a dict into a nested section would skip its environment;
        # building it through its constructor keeps the section's own prefix.
        if not isinstance(data, dict):
            return data
        for name, field in cls.model_fields.items():
            value = data.get(name)
            if isinstance(value, dict) and _is_section(field.annotation):
                data = {**data, name: field.annotation(**value)}
        return data
