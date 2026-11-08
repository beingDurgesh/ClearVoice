"""Device enumeration + classification, decoupled from sounddevice for testability.

`list_devices()` talks to PortAudio via sounddevice; everything else is pure
logic over DeviceInfo records, so it can be unit-tested with fake data.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


class DeviceRole(Enum):
    INPUT = "input"                    # physical mic (recording endpoint)
    OUTPUT = "output"                  # physical speaker (playback endpoint)
    CABLE_PLAYBACK = "cable_playback"  # virtual cable playback side (e.g. "CABLE Input") — ClearVoice writes here
    CABLE_RECORDING = "cable_recording"  # virtual cable recording side (e.g. "CABLE Output") — call apps read here
    BOTH = "both"


@dataclass(frozen=True)
class DeviceInfo:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    hostapi: str = ""

    @property
    def role(self) -> DeviceRole:
        return classify_role(self.name, self.max_input_channels, self.max_output_channels)


# Name patterns (lowercased) identifying virtual audio cables. Playback side of a
# cable is what an app WRITES to; recording side is what call apps READ from.
_CABLE_PLAYBACK_PATTERNS = ("cable input", "voicemeeter vaio", "voicemeeter aux vaio", "vb-audio point")
_CABLE_RECORDING_PATTERNS = ("cable output", "voicemeeter output", "voicemeeter aux output", "vb-audio virtual")


def classify_role(name: str, max_in: int, max_out: int) -> DeviceRole:
    n = name.lower()
    is_cable_in = any(p in n for p in _CABLE_PLAYBACK_PATTERNS)
    is_cable_out = any(p in n for p in _CABLE_RECORDING_PATTERNS)
    if is_cable_in and max_out > 0:
        return DeviceRole.CABLE_PLAYBACK
    if is_cable_out and max_in > 0:
        return DeviceRole.CABLE_RECORDING
    if max_in > 0 and max_out > 0:
        return DeviceRole.BOTH
    if max_in > 0:
        return DeviceRole.INPUT
    return DeviceRole.OUTPUT


def from_sounddevice(sd_devices: Iterable[dict], hostapi_names: Sequence[str] = ()) -> list[DeviceInfo]:
    out: list[DeviceInfo] = []
    for i, d in enumerate(sd_devices):
        hostapi = hostapi_names[d["hostapi"]] if d.get("hostapi") is not None and hostapi_names else str(d.get("hostapi", ""))
        out.append(
            DeviceInfo(
                index=i,
                name=d["name"],
                max_input_channels=d["max_input_channels"],
                max_output_channels=d["max_output_channels"],
                default_samplerate=float(d["default_samplerate"]),
                hostapi=hostapi,
            )
        )
    return out


def list_devices(sd_module=None) -> list[DeviceInfo]:
    """Enumerate all PortAudio devices via sounddevice (imported lazily)."""
    if sd_module is None:
        import sounddevice as sd_module  # local import so tests can avoid it
    hostapis = [h["name"] for h in sd_module.query_hostapis()]
    return from_sounddevice(list(sd_module.query_devices()), hostapis)


def inputs(devs: Sequence[DeviceInfo]) -> list[DeviceInfo]:
    """Microphone candidates: physical inputs (cable recording sides excluded)."""
    return [d for d in devs if d.max_input_channels > 0 and d.role in (DeviceRole.INPUT, DeviceRole.BOTH)]


def outputs(devs: Sequence[DeviceInfo]) -> list[DeviceInfo]:
    """Playback endpoints: physical speakers AND cable playback sides."""
    return [d for d in devs if d.max_output_channels > 0]


def virtual_cable_outputs(devs: Sequence[DeviceInfo]) -> list[DeviceInfo]:
    """Cable playback endpoints — the only correct 'processed output' for calls."""
    return [d for d in devs if d.role == DeviceRole.CABLE_PLAYBACK]


def has_virtual_cable(devs: Sequence[DeviceInfo]) -> bool:
    return bool(virtual_cable_outputs(devs)) and any(d.role == DeviceRole.CABLE_RECORDING for d in devs)


def find_default_input(devs: Sequence[DeviceInfo]) -> DeviceInfo | None:
    ins = inputs(devs)
    if not ins:
        return None
    # Prefer the system default input if present among them.
    try:
        import sounddevice as sd

        default_idx = sd.default.device[0]
        for d in ins:
            if d.index == default_idx:
                return d
    except Exception:
        pass
    return ins[0]
