import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from acex.config_map import ConfigMap
from acex.configuration import Configuration
from acex_devkit.models import ExternalValue
from acex_devkit.models.attribute_value import AttributeValue

from .compiled_logical_node import CompiledLogicalNode


class ConfigMapLoadError(Exception):
    """One or more files in a ConfigMap directory failed to import."""

    def __init__(self, failures: list[str]):
        self.failures = failures
        super().__init__("ConfigMaps failed to load:\n" + "\n".join(failures))


class ConfigCompiler:
    """
    This class enriches logical nodes with
    configuration from ConfigMaps.

    compile() is being run as the entrypoint
    1. Selects a logical node as self.ln, instancitating a CompiledLogicalNode
    2. Discovers processors and registers with CompiledLogicalNode.register()
    3. Discovers all ConfigMaps and registers those with matching ConfigMap.Filter.
    4. Runs all processors with CompiledLogicalNode.compile()
    """

    def __init__(self, db_manager):
        self.ln = None
        self.config_map_paths = []
        # Added in code or from a directory: kept for the life of the process.
        self._static_maps: list[ConfigMap] = []
        # Replaced as a whole while running (a git repository synced): key -> (root, [(name, map)]).
        # Never changed in place, only swapped, so a compile that is reading it is never disturbed.
        self._sources: dict[str, tuple[str, list[tuple[str, ConfigMap]]]] = {}
        self.db = db_manager

    @property
    def config_maps(self) -> list[ConfigMap]:
        sources = self._sources
        return [*self._static_maps, *(m for _, maps in sources.values() for _, m in maps)]

    @property
    def source_roots(self) -> list[str]:
        sources = self._sources
        return [*self.config_map_paths, *(root for root, _ in sources.values())]

    def add_config_map_path(self, dir_path: str):
        self.config_map_paths.append(dir_path)
        for _, config_map in self.load_config_maps(dir_path):
            self.add_config_map(config_map)

    def add_config_map(self, config_map: ConfigMap):
        """
        Adds a ConfigMap to the compiler.
        """
        self._static_maps.append(config_map)

    def set_source(self, key: str, root: str, config_maps: list[tuple[str, ConfigMap]]) -> None:
        """Use `config_maps` for source `key` from now on, in place of what it had."""
        self._sources = {**self._sources, key: (root, config_maps)}

    def remove_source(self, key: str) -> None:
        self._sources = {k: v for k, v in self._sources.items() if k != key}

    def source_names(self, key: str) -> list[str]:
        """The names of the ConfigMaps source `key` has loaded."""
        _, maps = self._sources.get(key, ("", []))
        return [name for name, _ in maps]

    def has_source(self, key: str) -> bool:
        return key in self._sources

    def source_keys(self) -> list[str]:
        return list(self._sources)

    def load_config_maps(self, dir_path: str, strict: bool = False) -> list[tuple[str, ConfigMap]]:
        """
        Finds all ConfigMaps in the given directory and subdirectories, named `<file>:<variable>`.

        A file that fails to import is skipped, unless `strict`: then nothing is returned and
        ConfigMapLoadError names every file that failed.
        """
        found = []
        failures = []
        for file_path in self._find_python_files_in_dir(dir_path):
            module_name = Path(file_path).stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            relative = os.path.relpath(file_path, dir_path)
            try:
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            except Exception as e:
                print(f"Failed to import {file_path}: {e}")
                failures.append(f"{relative}: {type(e).__name__}: {e}")
                continue
            # Hitta alla variabler som är instanser av ConfigMap (men inte klasser)
            for name, obj in module.__dict__.items():
                if isinstance(obj, ConfigMap) and not isinstance(obj, type):
                    found.append((f"{relative}:{name}", obj))
                    print(f"Registered ConfigMap instance: '{name}' from {file_path}")
        if strict and failures:
            raise ConfigMapLoadError(failures)
        return found

    def _find_python_files_in_dir(self, dir_path: str) -> list:
        """
        Recursively finds all .py files in the given directory and subdirectories.
        """
        py_files = []
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d != ".git"]
            for file in files:
                if file.endswith(".py"):
                    py_files.append(os.path.join(root, file))
        return py_files

    def _find_processors_for_ln(self):
        """
        Finds all processors that match the logical node's filters.
        This method should be implemented to discover and register processors.
        """
        for config_map in self.config_maps:
            if self.ln.check_config_map_filter(config_map):
                self.ln.register(config_map.compile)

    def _resolve_external_values(self, cln: CompiledLogicalNode):
        """
        Resolves all external values from CompiledLogicalNode.configuration.composed
        """
        print("Resolving ev!")
        session = next(self.db.get_session())
        try:
            for _, component in cln.configuration._components:
                for _k, v in component.model:
                    if v is not None:
                        if v.is_external():
                            print("resolve the ev.. ")

                            func = v.value._callable
                            value = func(v.value.kind, json.loads(v.value.query))
                            v.value = value

                            # save to db - upsert operation
                            try:
                                # Försök att hämta befintligt objekt
                                full_ref = v.metadata["attr_ptr"]
                                existing_ev = session.get(ExternalValue, full_ref)

                                if existing_ev:
                                    # Uppdatera befintligt objekt - bara value och resolved_at
                                    existing_ev.value = v.value
                                    existing_ev.resolved_at = datetime.now(UTC)

                                else:
                                    # Create new ev and save it.
                                    new_ev = ExternalValue(
                                        attr_ptr=full_ref,
                                        query=v.metadata["query"],
                                        value=v.value,
                                        kind=v.metadata["kind"],
                                        ev_type=v.metadata["ev_type"],
                                        plugin=v.metadata["plugin"],
                                        resolved_at=datetime.now(UTC),
                                    )
                                    session.add(new_ev)
                                # Save
                                session.commit()

                            except Exception as e:
                                session.rollback()
                                print(f"Error saving ExternalValue {full_ref}: {e}")
                                raise  # Re-raise för att stoppa hela operationen om något går fel

        finally:
            session.close()

    def _read_external_value_from_state(self, cln: CompiledLogicalNode):
        """
        Reads all EVs for compiled logical node and fetches last retrieved value
        from state database.

        TODO: Den här måste ha stöd för stackade komponenter?
        """
        session = next(self.db.get_session())
        try:
            # loop all config components of the cln
            for _, component in cln.configuration._components:
                # loop all attributes from the model.
                for _k, v in component.model:
                    if isinstance(v, AttributeValue):
                        # check all set attributes if theyre external.
                        if v.is_external():
                            # If external, set full reference
                            full_ref = v.metadata["attr_ptr"]
                            result = session.get(ExternalValue, full_ref)
                            if result is not None:
                                v.value = result.value
                                v.metadata["resolved"] = result.resolved
                                v.metadata["resolved_at"] = result.resolved_at
        finally:
            session.close()

    async def compile(self, logical_node, integrations, resolve: bool = False) -> dict:
        configuration = Configuration(logical_node.id, source_roots=self.source_roots)
        self.ln = CompiledLogicalNode(configuration, logical_node, integrations)
        self._find_processors_for_ln()
        await self.ln.compile()

        # Read values from state db
        if resolve is False:
            self._read_external_value_from_state(self.ln)
        else:
            self._resolve_external_values(self.ln)

        return self.ln
