from typing import Callable, Union, Awaitable, List
from acex.config_map import ConfigMap
from .compiled_logical_node import CompiledLogicalNode
from acex.configuration import Configuration
from acex.models import ExternalValue
from datetime import datetime, timezone
from ipaddress import IPv4Interface, IPv6Interface

import os
import importlib.util
import sys
from pathlib import Path
import inspect
import json

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
        self.config_maps = []
        self.db = db_manager

    def add_config_map_path(self, dir_path: str):
        self.config_map_paths.append(dir_path)
        self._find_and_register_config_maps(dir_path)

    def add_config_map(self, config_map: ConfigMap):
        """
        Adds a ConfigMap to the compiler.
        """
        self.config_maps.append(config_map)

    def _find_and_register_config_maps(self, dir_path: str):
        """
        Finds all ConfigMaps in the given directory and subdirectories and registers them.
        """
        py_files = self._find_python_files_in_dir(dir_path)
        for file_path in py_files:
            module_name = Path(file_path).stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            try:
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            except Exception as e:
                print(f"Failed to import {file_path}: {e}")
                continue
            # Hitta alla variabler som är instanser av ConfigMap (men inte klasser)
            for name, obj in module.__dict__.items():
                if isinstance(obj, ConfigMap) and not isinstance(obj, type):
                    self.add_config_map(obj)
                    print(f"Registered ConfigMap instance: '{name}' from {file_path}")

    def _find_python_files_in_dir(self, dir_path: str) -> list:
        """
        Recursively finds all .py files in the given directory and subdirectories.
        """
        py_files = []
        for root, _, files in os.walk(dir_path):
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
        Resolves all external values from CompiledLogicalNode.configuration.[attrs]
        """
        print("Resolving ev!")
        session = next(self.db.get_session())
        try:
            for _, ccomp in cln.configuration.components.items():
                for k, v in ccomp.attributes().items():
                    if isinstance(v.data, ExternalValue):
                        ev = v.data
                        func = ev._callable
                        value = func(ev.kind, json.loads(ev.query))
                        ev.value = value
                        ev.resolved_at = datetime.now(timezone.utc)

                        # save to db - upsert operation
                        try:
                            # Försök att hämta befintligt objekt
                            existing_ev = session.get(ExternalValue, ev.ref)
                            
                            if existing_ev:
                                # Uppdatera befintligt objekt - bara value och resolved_at
                                existing_ev.value = value
                                existing_ev.resolved_at = datetime.now(timezone.utc)
                            else:
                                # Skapa nytt objekt
                                new_ev = ExternalValue(
                                    ref=ev.ref,
                                    query=ev.query,
                                    value=value,
                                    kind=ev.kind,
                                    ev_type=ev.ev_type,
                                    plugin=ev.plugin,
                                    resolved_at=datetime.now(timezone.utc)
                                )
                                session.add(new_ev)
                            
                            session.commit()
                        except Exception as e:
                            session.rollback()
                            print(f"Error saving ExternalValue {ev.ref}: {e}")
                            raise  # Re-raise för att stoppa hela operationen om något går fel
        finally:
            session.close()


    def _read_external_value_from_state(self, cln: CompiledLogicalNode):
        """
        Reads all EVs for compiled logical node and fetches last retreived value
        from state database.
        """
        session = next(self.db.get_session())
        try:
            for _, ccomp in cln.configuration.components.items():
                for k, v in ccomp.attributes().items():
                    if isinstance(v.data, ExternalValue):
                        full_ref = f"{v.data.ref}"
                        result = session.get(ExternalValue, full_ref)

                        if result is not None:
                            setattr(v, "value", result.value)
                            setattr(v, "resolved_at", result.resolved_at)
        finally:
            session.close()

    def _map_all_ip_cidrs(self, cln):
        """
        Maps all ip ...
        """
        for _, ccom in cln.configuration.components.items():
            for k,v in ccom.attributes().items():
                if isinstance(v, IPv4Interface|IPv6Interface):
                    print(f"IP: {v} ")

    async def compile(self, logical_node, integrations, resolve: bool = False) -> dict:
        configuration = Configuration(logical_node.id) # Instanciates a config object
        self.ln = CompiledLogicalNode(configuration, logical_node, integrations)
        self._find_processors_for_ln()
        await self.ln.compile()

        # Read values from state db
        if resolve is False:
            self._read_external_value_from_state(self.ln)
        else:
            self._resolve_external_values(self.ln)

        self._map_all_ip_cidrs(self.ln)

        return self.ln.response

