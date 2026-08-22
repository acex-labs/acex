# resolver.py
import logging
import os
from typing import Any

import yaml as pyyaml

from acex_devkit.exceptions import RenderingError

logger = logging.getLogger(__name__)


def get_model(hardware_model: str, model_dir: str) -> dict[str, Any]:
    hardware_model = hardware_model.lower()

    filename = f"{hardware_model}.yaml"
    filepath = os.path.join(model_dir, filename)

    if os.path.exists(filepath):
        model_file = filepath
    else:
        model_file = os.path.join(model_dir, "cisco.yaml")
        logger.warning(
            "No model file for hardware model '%s', falling back to generic cisco.yaml",
            hardware_model,
        )

    if not os.path.exists(model_file):
        raise RenderingError(
            f"No device model file found for '{hardware_model}' "
            f"and no fallback 'cisco.yaml' in {model_dir}"
        )

    with open(model_file) as f:
        device_data = pyyaml.safe_load(f)

    if not device_data or "interfaces" not in device_data:
        raise RenderingError(
            f"Device model file '{model_file}' is empty or missing required 'interfaces' key"
        )

    return device_data
