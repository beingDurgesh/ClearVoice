"""Single-producer/single-consumer byte ring buffer.

Used on the INPUT side between the PortAudio real-time callback (producer) and
the worker thread (consumer). Under CPython's GIL, plain int index updates are
atomic (one bytecode store each), and bytearray slice assignment does not
release the GIL mid-copy, so a single writer + single reader need no lock.

Overflow policy matches the native ring: newest bytes are dropped and counted,
never overwriting unread data.
"""
from __future__ import annotations


def _next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p <<= 1
    return p


class ByteRing:
    def __init__(self, capacity: int):
        if capacity < 2:
            raise ValueError("capacity too small")
        self._cap = _next_pow2(capacity)
        self._mask = self._cap - 1
        self._buf = bytearray(self._cap)
        self._head = 0  # written by producer
        self._tail = 0  # written by consumer
        self.overflow = 0  # bytes dropped (producer side)

    def write(self, data) -> int:
        """Write bytes-like; returns bytes actually written (may be less if full)."""
        mv = memoryview(data).cast("B") if not isinstance(data, (bytes, bytearray)) else data
        n = len(mv)
        space = self._cap - (self._head - self._tail)
        w = n if n <= space else space
        if w < n:
            self.overflow += n - w
        h = self._head & self._mask  # buffer index = absolute index & mask
        end = h + w
        if end <= self._cap:
            self._buf[h:end] = mv[:w]
        else:
            first = self._cap - h
            self._buf[h:] = mv[:first]
            self._buf[: w - first] = mv[first:w]
        self._head += w  # single atomic store (GIL)
        return w

    def read(self, n: int) -> bytes:
        """Read up to n bytes; returns what was available."""
        avail = self._head - self._tail
        r = n if n < avail else avail
        if r <= 0:
            return b""
        t = self._tail & self._mask
        end = t + r
        if end <= self._cap:
            out = bytes(self._buf[t:end])
        else:
            first = self._cap - t
            out = bytes(self._buf[t:]) + bytes(self._buf[: r - first])
        self._tail += r  # single atomic store (GIL)
        return out

    @property
    def readable(self) -> int:
        return self._head - self._tail

    @property
    def writable(self) -> int:
        return self._cap - (self._head - self._tail)

    @property
    def capacity(self) -> int:
        return self._cap

    def reset(self) -> None:
        self._head = 0
        self._tail = 0
