"""Real-time audio pipeline for ClearVoice on Windows.

Threads:
  - PortAudio input callback (RT): copies raw bytes into ByteRing. Nothing else.
  - Worker thread: ByteRing -> CvProcessor (convert/resample/RNNoise) -> 48 kHz
    ring -> resample to output rate -> output float ring. Also computes meters.
  - PortAudio output callback (RT): reads output ring (zero-padded on underflow)
    into outdata. Nothing else.

The stream factory is injectable so unit tests can drive the callbacks manually
without audio hardware: stream_factory(kind, **kwargs) -> stream object with
start()/stop()/close() and a .callback attribute.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import numpy as np

from engine_binding.cv_core import CoreLib, CvEngineType, CvSampleFormat
from .byte_ring import ByteRing

CV_RATE = 48000
DEFAULT_BLOCKSIZE = 512  # frames per callback at the device rate (~10 ms @ 48 kHz)


@dataclass
class PipelineStats:
    running: bool = False
    engine_name: str = ""
    in_rate: int = 0
    out_rate: int = 0
    frames_processed: int = 0
    in_level_db: float = -120.0   # RMS dBFS of last input block
    out_level_db: float = -120.0  # RMS dBFS of last output block
    vad: float = -1.0
    peak_in_db: float = -120.0    # peak of raw input block, dBFS (for the quiet-mic hint)
    in_overflow: int = 0          # input ring drops (worker too slow)
    out_overflow: int = 0         # processor ring drops
    out_underflow: int = 0        # output ring starves (callback faster than worker) — cumulative
    startup_underflow: int = 0    # underflow samples in the first ~0.5 s after start
    steady_underflow: int = 0     # underflow samples after startup (clock drift / hiccups)
    drift_drops: int = 0          # samples the drift compensator skipped (producer side)
    buffer_delay_ms: float = 0.0  # output ring fill, ms
    max_buffer_ms: float = 250.0  # drift-compensation watermark
    cpu_percent: float = 0.0      # worker thread CPU (process_time based)
    error: str | None = None
    input_device: str = ""
    output_device: str = ""


def _rms_db(x: np.ndarray) -> float:
    if x.size == 0:
        return -120.0
    r = float(np.sqrt(np.mean(np.square(x.astype(np.float64)))))
    return 20.0 * np.log10(max(r, 1e-9))


def _peak_db(x: np.ndarray) -> float:
    if x.size == 0:
        return -120.0
    p = float(np.max(np.abs(x.astype(np.float64))))
    return 20.0 * np.log10(max(p, 1e-9))


class AudioPipeline:
    """Owns streams, rings, processor and the worker thread."""

    def __init__(self, core: CoreLib, stream_factory=None):
        self.core = core
        # stream_factory(kind: "input"|"output", **kwargs) -> stream-like object
        if stream_factory is None:
            stream_factory = _sounddevice_stream_factory
        self._stream_factory = stream_factory
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._in_stream = None
        self._out_stream = None
        self._processor = 0
        self._out_resampler = 0
        self._in_ring: ByteRing | None = None
        self._out_ring = 0  # native float ring (at out_rate)
        self._in_bytes_per_block = 0
        self._fmt = CvSampleFormat.FLOAT32
        self._dtype = np.float32
        self._in_ch = 1
        self._out_ch = 1
        self._in_rate = CV_RATE
        self._out_rate = CV_RATE
        self._blocksize = DEFAULT_BLOCKSIZE
        self._volume = 1.0
        self._input_gain_db = 0.0
        self._input_gain = 1.0
        self._mono_buf = np.empty(0, dtype=np.float32)
        self.stats = PipelineStats()
        self.tap = None  # optional callable(mono_float32_block) invoked in the output callback (test/diagnostic use)
        self._start_time = 0.0
        self._startup_underflow = 0
        self._startup_underflow_recorded = False
        self._max_buffer_ms = 250.0

    def set_max_buffer_ms(self, ms: float) -> None:
        self._max_buffer_ms = float(ms)
        self.stats.max_buffer_ms = self._max_buffer_ms

    # ------------------------------------------------------------ public API
    def start(
        self,
        in_device: int,
        out_device: int,
        in_name: str,
        out_name: str,
        in_rate: int,
        out_rate: int,
        in_channels: int,
        out_channels: int,
        engine: CvEngineType = CvEngineType.RNNOISE,
        blocksize: int = DEFAULT_BLOCKSIZE,
        dtype: np.dtype = np.float32,
        volume: float = 1.0,
    ) -> None:
        with self._lock:
            if self.stats.running:
                raise RuntimeError("pipeline already running")
            self._stop.clear()
            self.stats.error = None
            self._in_rate = int(in_rate)
            self._out_rate = int(out_rate)
            self._in_ch = max(1, min(int(in_channels), 8))
            self._out_ch = max(1, min(int(out_channels), 8))
            self._blocksize = int(blocksize)
            self._dtype = np.dtype(dtype)
            self._fmt = CoreLib.fmt_for_numpy(self._dtype)
            self._volume = float(volume)

            self._in_bytes_per_block = self._blocksize * self._in_ch * self._dtype.itemsize
            # input ring: hold ~0.5 s of raw audio
            self._in_ring = ByteRing(self._in_bytes_per_block * max(8, int(0.5 * self._in_rate / self._blocksize)))
            # processor: 48 kHz internal; its own output ring holds ~2 s at 48k
            self._processor = self.core.processor_create(
                engine, self._in_rate, self._in_ch, CV_RATE * 2
            )
            # output path: 48 kHz -> device rate, then a float ring at out_rate (~2 s)
            self._out_resampler = self.core.resampler_create(CV_RATE, self._out_rate)
            self._out_ring = self.core.ring_create(self._out_rate * 2)
            self._mono_buf = np.empty(self._blocksize, dtype=np.float32)
            self._rs_buf = np.empty(self._blocksize * 4 + 256, dtype=np.float32)

            self._in_stream = self._stream_factory(
                "input",
                device=in_device,
                channels=self._in_ch,
                samplerate=self._in_rate,
                blocksize=self._blocksize,
                dtype=np.dtype(self._dtype).name,
                callback=self._input_callback,
            )
            self._out_stream = self._stream_factory(
                "output",
                device=out_device,
                channels=self._out_ch,
                samplerate=self._out_rate,
                blocksize=self._blocksize,
                dtype="float32",
                callback=self._output_callback,
            )
            # Start capture first and let the worker prime the output ring for
            # ~50 ms before playback starts: avoids a burst of startup underflow.
            self._in_stream.start()
            time.sleep(0.05)
            self._out_stream.start()
            self._start_time = time.monotonic()
            self._startup_underflow_recorded = False
            # note: _max_buffer_ms is set in __init__ / set_max_buffer_ms, not reset here
            self._worker = threading.Thread(target=self._work_loop, name="clearvoice-worker", daemon=True)
            self._worker.start()
            self.stats.running = True
            self.stats.max_buffer_ms = self._max_buffer_ms
            self.stats.engine_name = self.core.processor_engine_name(self._processor)
            self.stats.in_rate = self._in_rate
            self.stats.out_rate = self._out_rate
            self.stats.input_device = in_name
            self.stats.output_device = out_name

    def stop(self) -> None:
        with self._lock:
            if not self.stats.running and self._worker is None:
                return
            self._stop.set()
            self.stats.running = False
        if self._worker is not None:
            self._worker.join(timeout=5.0)
            self._worker = None
        for s in (self._in_stream, self._out_stream):
            if s is not None:
                try:
                    s.stop()
                except Exception:
                    pass
                try:
                    s.close()
                except Exception:
                    pass
        self._in_stream = None
        self._out_stream = None
        with self._lock:
            if self._processor:
                self.core.processor_destroy(self._processor)
                self._processor = 0
            if self._out_resampler:
                self.core.resampler_destroy(self._out_resampler)
                self._out_resampler = 0
            if self._out_ring:
                self.core.ring_destroy(self._out_ring)
                self._out_ring = 0
            self._in_ring = None

    def set_volume(self, v: float) -> None:
        self._volume = float(v)

    def set_engine(self, engine: CvEngineType) -> int:
        """Hot-swap the suppression engine while running (0=OK). Worker-side call."""
        if not self._processor:
            return 1
        rc = self.core.processor_set_engine(self._processor, engine)
        if rc == 0:
            self.stats.engine_name = self.core.processor_engine_name(self._processor)
        return rc

    def set_input_gain(self, db: float) -> None:
        """Input gain in dB (default 0 = off). Applied in float domain with
        clipping protection before the engine."""
        self._input_gain_db = float(db)
        self._input_gain = 10.0 ** (self._input_gain_db / 20.0)

    # ------------------------------------------------------- RT callbacks
    def _input_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        # Real-time thread: memcpy into the ring, nothing else.
        try:
            if self._in_ring is not None:
                self._in_ring.write(memoryview(indata).cast("B"))
        except Exception as e:  # never raise into PortAudio
            self._report_error(f"input callback: {e}")

    def _output_callback(self, outdata: np.ndarray, frames: int, time_info, status) -> None:
        # Real-time thread: drain the native ring into outdata, nothing else.
        try:
            if self._out_ring and self._mono_buf.size >= frames:
                self.core.ring_read_padded(self._out_ring, self._mono_buf[:frames])
                if self.tap is not None:
                    self.tap(self._mono_buf[:frames].copy())  # pre-volume tap (memcpy only)
                outdata[:] = (self._mono_buf[:frames, None] * self._volume)
            else:
                outdata.fill(0.0)
        except Exception as e:  # never raise into PortAudio
            self._report_error(f"output callback: {e}")
            try:
                outdata.fill(0.0)
            except Exception:
                pass

    # --------------------------------------------------------- worker loop
    def _work_loop(self) -> None:
        t0 = time.perf_counter()
        c0 = time.process_time()
        blocks = 0
        try:
            while not self._stop.is_set():
                did_work = False
                ring = self._in_ring
                if ring is not None and ring.readable >= self._in_bytes_per_block:
                    raw = ring.read(self._in_bytes_per_block)
                    arr = np.frombuffer(raw, dtype=self._dtype)
                    self.stats.in_level_db = _rms_db(arr)
                    if self._dtype == np.float32 and self._input_gain == 1.0:
                        self.stats.peak_in_db = _peak_db(arr)
                        rc = self.core.processor_push(self._processor, arr, self._fmt)
                    else:
                        # convert to float32, apply input gain, protect against clipping
                        f = arr.astype(np.float32)
                        if self._dtype == np.int16:
                            f /= 32768.0
                        elif self._dtype == np.int32:
                            f /= 2147483648.0
                        self.stats.peak_in_db = _peak_db(f)
                        f *= self._input_gain
                        np.clip(f, -1.0, 1.0, out=f)
                        rc = self.core.processor_push(self._processor, f, CvSampleFormat.FLOAT32)
                    if rc != 0:
                        self._report_error(f"processor_push error code {rc}")
                    did_work = True
                    blocks += 1
                # drain processor output (48 kHz) -> resample -> output ring
                avail = self.core.processor_out_available(self._processor)
                if avail > 0:
                    n = min(avail, 4800)
                    buf48 = np.empty(n, dtype=np.float32)
                    got = self.core.processor_read_out(self._processor, buf48)
                    if got > 0:
                        n_out, rs = self.core.resampler_process(self._out_resampler, buf48[:got], self._rs_buf.size)
                        if n_out > 0:
                            # Bounded-latency drift compensation (producer side, safe):
                            # if the output ring is above the watermark, skip writing
                            # this block instead of letting the delay grow unbounded
                            # (happens when input and output clocks drift apart).
                            readable = self.core.ring_readable(self._out_ring)
                            watermark = int(self._max_buffer_ms / 1000.0 * self._out_rate)
                            if readable > watermark:
                                self.stats.drift_drops += n_out
                            else:
                                self.core.ring_write(self._out_ring, rs)
                                self.stats.out_level_db = _rms_db(rs)
                        did_work = True
                # stats
                self.stats.frames_processed = self.core.processor_frames_processed(self._processor)
                self.stats.vad = self.core.processor_last_vad(self._processor)
                self.stats.in_overflow = ring.overflow if ring else 0
                self.stats.out_overflow = self.core.processor_out_overflow(self._processor)
                total_underflow = self.core.ring_underflow(self._out_ring)
                if not self._startup_underflow_recorded and (time.monotonic() - self._start_time) >= 0.5:
                    self._startup_underflow_recorded = True
                    self._startup_underflow = total_underflow
                self.stats.out_underflow = total_underflow
                self.stats.startup_underflow = self._startup_underflow
                self.stats.steady_underflow = total_underflow - self._startup_underflow
                self.stats.buffer_delay_ms = 1000.0 * self.core.ring_readable(self._out_ring) / max(1, self._out_rate)
                now = time.perf_counter()
                dt = now - t0
                if dt >= 0.5:
                    self.stats.cpu_percent = 100.0 * (time.process_time() - c0) / dt
                    t0, c0 = now, time.process_time()
                if not did_work:
                    time.sleep(0.001)  # 1 ms poll; no locks shared with RT callbacks
        except Exception as e:  # worker must never die silently
            self._report_error(f"worker: {e}")

    def _report_error(self, msg: str) -> None:
        # Last error wins; GUI polls stats.error. Never raise from here.
        self.stats.error = msg


def _sounddevice_stream_factory(kind: str, **kwargs):
    import sounddevice as sd

    if kind == "input":
        return sd.InputStream(**kwargs)
    return sd.OutputStream(**kwargs)
