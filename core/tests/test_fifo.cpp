#include "test_framework.h"
#include "frame_fifo.h"

#include <vector>

using clearvoice::FrameFifo;

TEST(fifo_partial_pops) {
    FrameFifo f;
    std::vector<float> in(100);
    for (int i = 0; i < 100; ++i) in[i] = static_cast<float>(i);
    f.push(in.data(), 100);
    CHECK(f.size() == 100);
    std::vector<float> out(100, -1.0f);
    CHECK(f.pop(out.data(), 30) == 30);
    CHECK(f.pop(out.data() + 30, 30) == 30);
    CHECK(f.pop(out.data() + 60, 30) == 30);
    CHECK(f.pop(out.data() + 90, 30) == 10); // only 10 left
    CHECK(f.size() == 0);
    for (int i = 0; i < 100; ++i) CHECK(out[i] == static_cast<float>(i));
}

TEST(fifo_engine_sized_frames) {
    FrameFifo f;
    const int FS = 480;
    const size_t chunks[] = {137, 512, 64, 800, 477};
    size_t total = 0;
    for (size_t c : chunks) total += c;
    std::vector<float> in(total);
    for (size_t i = 0; i < in.size(); ++i) in[i] = static_cast<float>(i % 997);
    // push in odd-sized chunks, like a real callback would
    size_t off = 0;
    for (size_t c : chunks) {
        f.push(in.data() + off, c);
        off += c;
    }
    CHECK(off == in.size());
    std::vector<float> frame(FS, 0.0f);
    int frames = 0;
    std::vector<float> all;
    while (f.size() >= static_cast<size_t>(FS)) { // producer pattern: only pop full frames
        CHECK(f.pop(frame.data(), FS) == static_cast<size_t>(FS));
        all.insert(all.end(), frame.begin(), frame.end());
        ++frames;
    }
    CHECK(frames == static_cast<int>(total / FS));
    CHECK(f.size() == total % FS);
    for (size_t i = 0; i < all.size(); ++i) CHECK(all[i] == in[i]);
}
