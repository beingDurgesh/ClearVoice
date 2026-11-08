"""ByteRing correctness + threaded stress test."""
from __future__ import annotations

import threading
import time

from audio.byte_ring import ByteRing


def test_basic_write_read():
    r = ByteRing(1024)
    data = bytes(range(256))
    assert r.write(data) == 256
    assert r.readable == 256
    assert r.read(256) == data
    assert r.readable == 0


def test_wraparound_preserves_order():
    r = ByteRing(256)
    for round_ in range(20):
        chunk = bytes([round_ % 256]) * 200
        assert r.write(chunk) == 200
        assert r.read(200) == chunk
    assert r.overflow == 0


def test_overflow_drops_newest_and_counts():
    r = ByteRing(64)
    assert r.write(b"x" * 100) == 64
    assert r.overflow == 36
    assert r.read(64) == b"x" * 64


def test_partial_read():
    r = ByteRing(128)
    r.write(b"abcdef")
    assert r.read(4) == b"abcd"
    assert r.read(10) == b"ef"
    assert r.read(1) == b""


def test_threaded_stress_no_loss_no_reorder():
    r = ByteRing(1 << 16)
    total = 200_000
    produced = bytearray()
    consumed = bytearray()
    errors: list[str] = []

    def producer():
        sent = 0
        while sent < total:
            chunk = bytes([sent % 251]) * 997
            piece = chunk[: min(997, total - sent)]
            n = r.write(piece)
            produced.extend(piece[:n])
            sent += n
            if n == 0:
                time.sleep(0.001)  # ring momentarily full; consumer is draining

    def consumer():
        got = 0
        while got < total:
            data = r.read(1500)
            if not data:
                time.sleep(0.0005)  # avoid starving the producer under the GIL
                continue
            consumed.extend(data)
            got += len(data)

    t1 = threading.Thread(target=producer)
    t2 = threading.Thread(target=consumer)
    t2.start()
    t1.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert not t1.is_alive() and not t2.is_alive(), "threads hung"
    assert not errors
    # data integrity: everything the producer accepted must arrive in order
    assert bytes(consumed[:total]) == bytes(produced[:total])
    # a tight producer CAN momentarily outpace the sleeping consumer; drops are
    # counted (never silent) but must stay a small fraction of the stream
    assert r.overflow < total * 0.05, f"overflow {r.overflow} too large"
