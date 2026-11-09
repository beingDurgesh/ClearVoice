"""Audio device enumeration and virtual-cable detection."""
from .manager import (
    DeviceInfo,
    DeviceRole,
    list_devices,
    inputs,
    outputs,
    virtual_cable_outputs,
    has_virtual_cable,
    find_default_input,
    dedupe_devices,
)

__all__ = [
    "DeviceInfo",
    "DeviceRole",
    "list_devices",
    "inputs",
    "outputs",
    "virtual_cable_outputs",
    "has_virtual_cable",
    "find_default_input",
    "dedupe_devices",
]
