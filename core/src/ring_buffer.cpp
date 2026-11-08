#include "ring_buffer.h"

#include <algorithm>
#include <cstring>

namespace clearvoice {

static size_t nextPow2(size_t n) {
    size_t p = 1;
    while (p < n) p <<= 1;
    return p;
}

RingBuffer::RingBuffer(size_t capacity)
    : capacity_(nextPow2(std::max<size_t>(capacity, 2))), mask_(capacity_ - 1), buf_(capacity_) {}

size_t RingBuffer::write(const float* src, size_t n) {
    const size_t h = head_.load(std::memory_order_relaxed);
    const size_t t = tail_.load(std::memory_order_acquire);
    const size_t space = capacity_ - (h - t);
    const size_t w = std::min(n, space);
    if (w < n) {
        // Ring full: drop the newest samples, never overwrite unread data.
        overflow_.fetch_add(n - w, std::memory_order_relaxed);
    }
    for (size_t i = 0; i < w; ++i) {
        buf_[(h + i) & mask_] = src[i];
    }
    head_.store(h + w, std::memory_order_release);
    return w;
}

size_t RingBuffer::read(float* dst, size_t n) {
    const size_t t = tail_.load(std::memory_order_relaxed);
    const size_t h = head_.load(std::memory_order_acquire);
    const size_t avail = h - t;
    const size_t r = std::min(n, avail);
    for (size_t i = 0; i < r; ++i) {
        dst[i] = buf_[(t + i) & mask_];
    }
    tail_.store(t + r, std::memory_order_release);
    return r;
}

size_t RingBuffer::readPadded(float* dst, size_t n) {
    const size_t r = read(dst, n);
    if (r < n) {
        std::memset(dst + r, 0, (n - r) * sizeof(float));
        underflow_.fetch_add(n - r, std::memory_order_relaxed);
    }
    return r;
}

void RingBuffer::reset() {
    tail_.store(0, std::memory_order_relaxed);
    head_.store(0, std::memory_order_release);
}

} // namespace clearvoice
