#include "frame_fifo.h"

#include <algorithm>
#include <cstring>

namespace clearvoice {

void FrameFifo::push(const float* src, size_t n) {
    data_.insert(data_.end(), src, src + n);
}

size_t FrameFifo::pop(float* dst, size_t n) {
    const size_t avail = size();
    const size_t r = std::min(n, avail);
    if (r > 0) {
        std::memcpy(dst, data_.data() + offset_, r * sizeof(float));
        offset_ += r;
    }
    // Compact when the consumed prefix is large, to bound memory growth.
    if (offset_ > 65536 && offset_ > data_.size() / 2) {
        data_.erase(data_.begin(), data_.begin() + static_cast<long>(offset_));
        offset_ = 0;
    }
    return r;
}

void FrameFifo::clear() {
    data_.clear();
    offset_ = 0;
}

} // namespace clearvoice
