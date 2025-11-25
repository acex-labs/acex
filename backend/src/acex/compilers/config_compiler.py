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
        Resolves all external values from CompiledLogicalNode.configuration.composed
        """
        print("Resolving ev!")
        # TODO: Migrate to use cln.configuration.composed instead of components
        # session = next(self.db.get_session())
        # try:
        #     # Need to recursively walk through composed structure to find AttributeValue objects
        #     pass
        # finally:
        #     session.close()


    def _read_external_value_from_state(self, cln: CompiledLogicalNode):
        """
        Reads all EVs for compiled logical node and fetches last retrieved value
        from state database.
        """
        session = next(self.db.get_session())
        try:
            
            for _, component in cln.configuration._components:
                print("-" * 50)
                
                # TODO: hur får vi ut alla attribut för componenten så vi kan editera dom? 
                print(type(component))
                for k,v in component.model:
                    print(f"k: {k} of t: {type(v.value)}")
                    if isinstance(v.value, ExternalValue):
                        print("Den här är external! :) ")
                    print("-")
                






            # for _, ccomp in cln.configuration.components.items():
            #     for k, v in ccomp.attributes().items():
            #         if isinstance(v.data, ExternalValue):
            #             full_ref = f"{v.data.ref}"
            #             result = session.get(ExternalValue, full_ref)

            #             if result is not None:
            #                 setattr(v, "value", result.value)
            #                 setattr(v, "resolved_at", result.resolved_at)
        finally:
            session.close()




    def _map_all_ip_cidrs(self, cln):
        """
        Maps all ip addresses
        """
        # TODO: Migrate to use cln.configuration.composed instead of components
        # for _, ccom in cln.configuration.components.items():
        #     for k,v in ccom.attributes().items():
        #         if isinstance(v, IPv4Interface|IPv6Interface):
        #             print(f"IP: {v} ")
        pass

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

