"""Device classification tests with synthetic device lists (no hardware needed)."""
from __future__ import annotations

from devices.manager import (
    DeviceInfo,
    DeviceRole,
    classify_role,
    from_sounddevice,
    has_virtual_cable,
    inputs,
    outputs,
    virtual_cable_outputs,
)


def _dev(i, name, chin, chout, rate=48000.0):
    return DeviceInfo(index=i, name=name, max_input_channels=chin, max_output_channels=chout, default_samplerate=rate)


FAKE_DEVICES = [
    _dev(0, "Microphone (Realtek USB Audio)", 1, 0, 48000.0),
    _dev(1, "Speakers (Realtek USB Audio)", 0, 2, 48000.0),
    _dev(2, "CABLE Input (VB-Audio Virtual Cable)", 0, 2, 44100.0),
    _dev(3, "CABLE Output (VB-Audio Virtual Cable)", 2, 0, 44100.0),
]


def test_classify_roles():
    assert classify_role("Microphone (USB)", 1, 0) == DeviceRole.INPUT
    assert classify_role("Speakers", 0, 2) == DeviceRole.OUTPUT
    assert classify_role("CABLE Input (VB-Audio Virtual Cable)", 0, 2) == DeviceRole.CABLE_PLAYBACK
    assert classify_role("CABLE Output (VB-Audio Virtual Cable)", 2, 0) == DeviceRole.CABLE_RECORDING
    assert classify_role("Voicemeeter VAIO", 0, 2) == DeviceRole.CABLE_PLAYBACK


def test_inputs_exclude_cable_recording_side():
    ins = inputs(FAKE_DEVICES)
    assert [d.name for d in ins] == ["Microphone (Realtek USB Audio)"]


def test_outputs_include_cable_playback():
    outs = outputs(FAKE_DEVICES)
    names = [d.name for d in outs]
    assert "CABLE Input (VB-Audio Virtual Cable)" in names
    assert "Speakers (Realtek USB Audio)" in names


def test_virtual_cable_detection():
    assert has_virtual_cable(FAKE_DEVICES)
    cables = virtual_cable_outputs(FAKE_DEVICES)
    assert len(cables) == 1 and cables[0].name.startswith("CABLE Input")
    # without a cable:
    no_cable = [d for d in FAKE_DEVICES if "CABLE" not in d.name]
    assert not has_virtual_cable(no_cable)
    assert virtual_cable_outputs(no_cable) == []


def test_from_sounddevice_dicts():
    raw = [
        {"name": "Mic", "max_input_channels": 2, "max_output_channels": 0, "default_samplerate": 44100, "hostapi": 0},
        {"name": "Spk", "max_input_channels": 0, "max_output_channels": 2, "default_samplerate": 48000, "hostapi": 1},
    ]
    devs = from_sounddevice(raw, ["WASAPI", "MME"])
    assert devs[0].hostapi == "WASAPI" and devs[0].default_samplerate == 44100.0
    assert devs[1].role == DeviceRole.OUTPUT
