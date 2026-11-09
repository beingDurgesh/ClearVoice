"""ctypes wrapper around clearvoice_core.dll / libclearvoice_core.so.

This is the only place that talks to the native library. All functions are
thin, typed wrappers; numpy arrays are passed as raw pointers (zero-copy).
"""
from __future__ import annotations

import ctypes
import os
import sys
from enum import IntEnum
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]


class CvEngineType(IntEnum):
    PASSTHROUGH = 0
    RNNOISE = 1


class CvSampleFormat(IntEnum):
    INT16 = 0
    INT32 = 1
    FLOAT32 = 2


_NUMPY_TO_FMT = {
    np.dtype("int16"): CvSampleFormat.INT16,
    np.dtype("int32"): CvSampleFormat.INT32,
    np.dtype("float32"): CvSampleFormat.FLOAT32,
}


def find_dll_path() -> Path:
    """Locate the native library: env override, frozen bundle, then the CMake build tree."""
    env = os.environ.get("CLEARVOICE_DLL")
    if env:
        p = Path(env)
        if p.exists():
            return p
        raise FileNotFoundError(f"CLEARVOICE_DLL points to missing file: {env}")
    candidates = []
    if getattr(sys, "frozen", False):  # PyInstaller onefile/onedir
        candidates.append(Path(sys._MEIPASS) / "clearvoice_core.dll")  # type: ignore[attr-defined]
    candidates += [
        REPO_ROOT / "build" / "core" / "Release" / "clearvoice_core.dll",
        REPO_ROOT / "build" / "core" / "clearvoice_core.dll",
        Path(__file__).resolve().parent / "clearvoice_core.dll",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        "clearvoice_core library not found. Build it first (see README.md) or set CLEARVOICE_DLL. "
        f"Searched: {[str(c) for c in candidates]}"
    )


class CoreLib:
    """Typed ctypes handle to the ClearVoice core library."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else find_dll_path()
        self.lib = ctypes.CDLL(str(self.path))
        self._declare()

    # ------------------------------------------------------------------ setup
    def _declare(self) -> None:
        L = self.lib
        c = ctypes
        L.cv_version.restype = c.c_char_p
        L.cv_version.argtypes = []
        # engine
        L.cv_engine_create.restype = c.c_void_p
        L.cv_engine_create.argtypes = [c.c_int]
        L.cv_engine_destroy.restype = None
        L.cv_engine_destroy.argtypes = [c.c_void_p]
        L.cv_engine_frame_size.restype = c.c_int
        L.cv_engine_frame_size.argtypes = [c.c_void_p]
        L.cv_engine_name.restype = c.c_char_p
        L.cv_engine_name.argtypes = [c.c_void_p]
        L.cv_engine_type_name.restype = c.c_char_p
        L.cv_engine_type_name.argtypes = [c.c_int]
        L.cv_engine_process_frame.restype = c.c_float
        L.cv_engine_process_frame.argtypes = [c.c_void_p, c.POINTER(c.c_float), c.POINTER(c.c_float)]
        # ring
        L.cv_ring_create.restype = c.c_void_p
        L.cv_ring_create.argtypes = [c.c_size_t]
        L.cv_ring_destroy.restype = None
        L.cv_ring_destroy.argtypes = [c.c_void_p]
        L.cv_ring_write.restype = c.c_size_t
        L.cv_ring_write.argtypes = [c.c_void_p, c.POINTER(c.c_float), c.c_size_t]
        L.cv_ring_read.restype = c.c_size_t
        L.cv_ring_read.argtypes = [c.c_void_p, c.POINTER(c.c_float), c.c_size_t]
        L.cv_ring_read_padded.restype = c.c_size_t
        L.cv_ring_read_padded.argtypes = [c.c_void_p, c.POINTER(c.c_float), c.c_size_t]
        L.cv_ring_readable.restype = c.c_size_t
        L.cv_ring_readable.argtypes = [c.c_void_p]
        L.cv_ring_writable.restype = c.c_size_t
        L.cv_ring_writable.argtypes = [c.c_void_p]
        L.cv_ring_overflow_count.restype = c.c_ulonglong
        L.cv_ring_overflow_count.argtypes = [c.c_void_p]
        L.cv_ring_underflow_count.restype = c.c_ulonglong
        L.cv_ring_underflow_count.argtypes = [c.c_void_p]
        L.cv_ring_reset.restype = None
        L.cv_ring_reset.argtypes = [c.c_void_p]
        # resampler
        L.cv_resampler_create.restype = c.c_void_p
        L.cv_resampler_create.argtypes = [c.c_int, c.c_int]
        L.cv_resampler_destroy.restype = None
        L.cv_resampler_destroy.argtypes = [c.c_void_p]
        L.cv_resampler_process.restype = c.c_size_t
        L.cv_resampler_process.argtypes = [c.c_void_p, c.POINTER(c.c_float), c.c_size_t, c.POINTER(c.c_float), c.c_size_t]
        # processor
        L.cv_processor_create.restype = c.c_void_p
        L.cv_processor_create.argtypes = [c.c_int, c.c_int, c.c_int, c.c_size_t]
        L.cv_processor_destroy.restype = None
        L.cv_processor_destroy.argtypes = [c.c_void_p]
        L.cv_processor_push.restype = c.c_int
        L.cv_processor_push.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t, c.c_int]
        L.cv_processor_read_out.restype = c.c_size_t
        L.cv_processor_read_out.argtypes = [c.c_void_p, c.POINTER(c.c_float), c.c_size_t]
        L.cv_processor_out_available.restype = c.c_size_t
        L.cv_processor_out_available.argtypes = [c.c_void_p]
        L.cv_processor_last_vad.restype = c.c_float
        L.cv_processor_last_vad.argtypes = [c.c_void_p]
        L.cv_processor_frames_processed.restype = c.c_ulonglong
        L.cv_processor_frames_processed.argtypes = [c.c_void_p]
        L.cv_processor_out_overflow.restype = c.c_ulonglong
        L.cv_processor_out_overflow.argtypes = [c.c_void_p]
        L.cv_processor_in_rate.restype = c.c_int
        L.cv_processor_in_rate.argtypes = [c.c_void_p]
        L.cv_processor_in_channels.restype = c.c_int
        L.cv_processor_in_channels.argtypes = [c.c_void_p]
        L.cv_processor_engine_name.restype = c.c_char_p
        L.cv_processor_engine_name.argtypes = [c.c_void_p]
        L.cv_processor_set_engine.restype = c.c_int
        L.cv_processor_set_engine.argtypes = [c.c_void_p, c.c_int]
        L.cv_processor_set_hpf.restype = c.c_int
        L.cv_processor_set_hpf.argtypes = [c.c_void_p, c.c_int, c.c_float]

    # ------------------------------------------------------------- utilities
    @staticmethod
    def _fptr(arr: np.ndarray) -> ctypes.POINTER(ctypes.c_float):
        return arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

    def version(self) -> str:
        return self.lib.cv_version().decode()

    # ---------------------------------------------------------------- engine
    def engine_create(self, type_: CvEngineType) -> int:
        h = self.lib.cv_engine_create(int(type_))
        if not h:
            raise RuntimeError(f"cv_engine_create({type_}) failed")
        return h

    def engine_destroy(self, h: int) -> None:
        self.lib.cv_engine_destroy(h)

    def engine_frame_size(self, h: int) -> int:
        return self.lib.cv_engine_frame_size(h)

    def engine_name(self, h: int) -> str:
        return self.lib.cv_engine_name(h).decode()

    def engine_type_name(self, type_: CvEngineType) -> str:
        return self.lib.cv_engine_type_name(int(type_)).decode()

    def engine_process_frame(self, h: int, in_: np.ndarray) -> tuple[float, np.ndarray]:
        """Process one 480-sample float32 mono frame. Returns (vad, out)."""
        fs = self.engine_frame_size(h)
        assert in_.dtype == np.float32 and in_.size == fs
        out = np.empty(fs, dtype=np.float32)
        vad = self.lib.cv_engine_process_frame(h, self._fptr(out), self._fptr(in_))
        return vad, out

    # ------------------------------------------------------------------ ring
    def ring_create(self, capacity: int) -> int:
        h = self.lib.cv_ring_create(capacity)
        if not h:
            raise RuntimeError("cv_ring_create failed")
        return h

    def ring_destroy(self, h: int) -> None:
        self.lib.cv_ring_destroy(h)

    def ring_write(self, h: int, data: np.ndarray) -> int:
        return self.lib.cv_ring_write(h, self._fptr(data), data.size)

    def ring_read(self, h: int, dst: np.ndarray) -> int:
        return self.lib.cv_ring_read(h, self._fptr(dst), dst.size)

    def ring_read_padded(self, h: int, dst: np.ndarray) -> int:
        """Read up to dst.size samples, zero-filling shortfall (RT-thread safe)."""
        return self.lib.cv_ring_read_padded(h, self._fptr(dst), dst.size)

    def ring_readable(self, h: int) -> int:
        return self.lib.cv_ring_readable(h)

    def ring_overflow(self, h: int) -> int:
        return self.lib.cv_ring_overflow_count(h)

    def ring_underflow(self, h: int) -> int:
        return self.lib.cv_ring_underflow_count(h)

    # ------------------------------------------------------------- resampler
    def resampler_create(self, in_rate: int, out_rate: int) -> int:
        h = self.lib.cv_resampler_create(in_rate, out_rate)
        if not h:
            raise RuntimeError(f"cv_resampler_create({in_rate},{out_rate}) failed")
        return h

    def resampler_destroy(self, h: int) -> None:
        self.lib.cv_resampler_destroy(h)

    def resampler_process(self, h: int, in_: np.ndarray, out_capacity: int) -> tuple[int, np.ndarray]:
        out = np.empty(out_capacity, dtype=np.float32)
        n = self.lib.cv_resampler_process(h, self._fptr(in_), in_.size, self._fptr(out), out.size)
        return n, out[:n]

    # ------------------------------------------------------------- processor
    def processor_create(self, engine: CvEngineType, in_rate: int, in_channels: int, out_ring_capacity: int) -> int:
        h = self.lib.cv_processor_create(int(engine), in_rate, in_channels, out_ring_capacity)
        if not h:
            raise RuntimeError("cv_processor_create failed (bad args or engine init failed)")
        return h

    def processor_destroy(self, h: int) -> None:
        self.lib.cv_processor_destroy(h)

    def processor_push(self, h: int, data: np.ndarray, fmt: CvSampleFormat) -> int:
        """data: interleaved samples of dtype matching fmt. Returns CvError code (0=OK)."""
        frames = data.size // self.processor_in_channels(h)
        return self.lib.cv_processor_push(h, data.ctypes.data_as(ctypes.c_void_p), frames, int(fmt))

    def processor_read_out(self, h: int, dst: np.ndarray) -> int:
        return self.lib.cv_processor_read_out(h, self._fptr(dst), dst.size)

    def processor_out_available(self, h: int) -> int:
        return self.lib.cv_processor_out_available(h)

    def processor_last_vad(self, h: int) -> float:
        return self.lib.cv_processor_last_vad(h)

    def processor_frames_processed(self, h: int) -> int:
        return self.lib.cv_processor_frames_processed(h)

    def processor_out_overflow(self, h: int) -> int:
        return self.lib.cv_processor_out_overflow(h)

    def processor_in_rate(self, h: int) -> int:
        return self.lib.cv_processor_in_rate(h)

    def processor_in_channels(self, h: int) -> int:
        return self.lib.cv_processor_in_channels(h)

    def processor_engine_name(self, h: int) -> str:
        return self.lib.cv_processor_engine_name(h).decode()

    def processor_set_engine(self, h: int, engine: CvEngineType) -> int:
        """Hot-swap engine (worker thread only). Returns CvError (0=OK)."""
        return self.lib.cv_processor_set_engine(h, int(engine))

    def processor_set_hpf(self, h: int, enable: bool, cutoff_hz: float = 80.0) -> int:
        """Optional pre-engine high-pass (default off). Returns CvError (0=OK)."""
        return self.lib.cv_processor_set_hpf(h, 1 if enable else 0, float(cutoff_hz))

    @staticmethod
    def fmt_for_numpy(dtype: np.dtype) -> CvSampleFormat:
        try:
            return _NUMPY_TO_FMT[np.dtype(dtype)]
        except KeyError:
            raise ValueError(f"unsupported dtype {dtype}; use int16/int32/float32")
