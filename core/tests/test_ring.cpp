#include "test_framework.h"
#include "ring_buffer.h"

#include <vector>

using clearvoice::RingBuffer;

TEST(ring_basic_write_read) {
    RingBuffer r(1024);
    std::vector<float> in(100), out(100, 0.0f);
    for (int i = 0; i < 100; ++i) in[i] = static_cast<float>(i) * 0.5f;
    CHECK(r.write(in.data(), 100) == 100);
    CHECK(r.readable() == 100);
    CHECK(r.writable() == 1024 - 100);
    CHECK(r.read(out.data(), 100) == 100);
    for (int i = 0; i < 100; ++i) CHECK(out[i] == in[i]);
    CHECK(r.readable() == 0);
}

TEST(ring_wraparound) {
    RingBuffer r(256); // pow2
    std::vector<float> in(200), out(200, 0.0f);
    for (int round = 0; round < 10; ++round) {
        for (int i = 0; i < 200; ++i) in[i] = static_cast<float>(round * 1000 + i);
        CHECK(r.write(in.data(), 200) == 200);
        CHECK(r.read(out.data(), 200) == 200);
        for (int i = 0; i < 200; ++i) CHECK(out[i] == in[i]);
    }
    CHECK(r.overflowCount() == 0);
    CHECK(r.underflowCount() == 0);
}

TEST(ring_overflow_drops_newest_and_counts) {
    RingBuffer r(64);
    std::vector<float> in(100, 1.0f);
    CHECK(r.write(in.data(), 100) == 64); // only 64 fit
    CHECK(r.overflowCount() == 36);
    CHECK(r.readable() == 64);
    std::vector<float> out(64, 0.0f);
    CHECK(r.read(out.data(), 64) == 64);
    for (float v : out) CHECK(v == 1.0f);
}

TEST(ring_read_padded_underflow) {
    RingBuffer r(128);
    std::vector<float> out(10, 9.0f);
    CHECK(r.readPadded(out.data(), 10) == 0); // nothing available
    for (float v : out) CHECK(v == 0.0f);      // zero-filled
    CHECK(r.underflowCount() == 10);
}

TEST(ring_reset) {
    RingBuffer r(64);
    std::vector<float> in(10, 1.0f);
    CHECK(r.write(in.data(), 10) == 10);
    r.reset();
    CHECK(r.readable() == 0);
    CHECK(r.write(in.data(), 10) == 10);
}
