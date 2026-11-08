#!/usr/bin/env python3
"""Smoke test: load clearvoice_core.dll via ctypes (the exact FFI path Phase 3 uses)
and exercise the C API end to end."""
import ctypes
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DLL = ROOT / "build" / "core" / "Release" / "clearvoice_core.dll"

lib = ctypes.CDLL(str(DLL))
lib.cv_version.restype = ctypes.c_char_p
lib.cv_engine_create.restype = ctypes.c_void_p
lib.cv_engine_create.argtypes = [ctypes.c_int]
lib.cv_engine_destroy.argtypes = [ctypes.c_void_p]
lib.cv_engine_frame_size.restype = ctypes.c_int
lib.cv_engine_frame_size.argtypes = [ctypes.c_void_p]
lib.cv_engine_name.restype = ctypes.c_char_p
lib.cv_engine_name.argtypes = [ctypes.c_void_p]
lib.cv_engine_process_frame.restype = ctypes.c_float
lib.cv_engine_process_frame.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
lib.cv_processor_create.restype = ctypes.c_void_p
lib.cv_processor_create.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_size_t]
lib.cv_processor_destroy.argtypes = [ctypes.c_void_p]
lib.cv_processor_push.restype = ctypes.c_int
lib.cv_processor_push.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
lib.cv_processor_read_out.restype = ctypes.c_size_t
lib.cv_processor_read_out.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_size_t]
lib.cv_processor_out_available.restype = ctypes.c_size_t
lib.cv_processor_out_available.argtypes = [ctypes.c_void_p]
lib.cv_processor_last_vad.restype = ctypes.c_float
lib.cv_processor_last_vad.argtypes = [ctypes.c_void_p]
lib.cv_processor_frames_processed.restype = ctypes.c_ulonglong
lib.cv_processor_frames_processed.argtypes = [ctypes.c_void_p]
lib.cv_processor_engine_name.restype = ctypes.c_char_p
lib.cv_processor_engine_name.argtypes = [ctypes.c_void_p]

print("cv_version:", lib.cv_version().decode())

# --- raw engine ---
e = lib.cv_engine_create(1)  # CV_ENGINE_RNNOISE
assert e, "engine create failed"
fs = lib.cv_engine_frame_size(e)
print("engine:", lib.cv_engine_name(e).decode(), "frame_size:", fs)
assert fs == 480
rng = np.random.default_rng(42)
inp = rng.standard_normal(fs).astype(np.float32) * 0.9
out = np.zeros(fs, dtype=np.float32)
vad = lib.cv_engine_process_frame(e, out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                                  inp.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
print(f"frame: vad={vad:.4f} rms_in={np.sqrt((inp**2).mean()):.4f} rms_out={np.sqrt((out**2).mean()):.4f}")
assert 0.0 <= vad <= 1.0
assert np.isfinite(out).all()
lib.cv_engine_destroy(e)

# --- full processor: 44.1 kHz stereo int16 in -> 48 kHz mono float out ---
p = lib.cv_processor_create(1, 44100, 2, 1 << 16)
assert p, "processor create failed"
print("processor engine:", lib.cv_processor_engine_name(p).decode())
frames = 4410  # 0.1 s
stereo = (rng.standard_normal(frames * 2) * 16000).astype(np.int16)
rc = lib.cv_processor_push(p, stereo.ctypes.data_as(ctypes.c_void_p), frames, 0)  # CV_FMT_INT16
assert rc == 0, f"push rc={rc}"
avail = lib.cv_processor_out_available(p)
print("frames_processed:", lib.cv_processor_frames_processed(p), "out_available:", avail, "last_vad:", lib.cv_processor_last_vad(p))
buf = np.zeros(avail, dtype=np.float32)
got = lib.cv_processor_read_out(p, buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), avail)
print("read_out:", got, "finite:", bool(np.isfinite(buf).all()), "rms:", float(np.sqrt((buf**2).mean())))
assert got == avail and np.isfinite(buf).all()
lib.cv_processor_destroy(p)
print("SMOKE TEST OK")
