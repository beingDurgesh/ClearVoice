#pragma once
/* Accumulator that turns arbitrary-size blocks into fixed-size engine frames.
 * Single-threaded (used on the worker thread only). */
#include <cstddef>
#include <vector>

namespace clearvoice {

class FrameFifo {
public:
    void push(const float* src, size_t n);
    /* Pop up to n samples; returns how many were popped. */
    size_t pop(float* dst, size_t n);
    size_t size() const { return data_.size() - offset_; }
    void clear();

private:
    std::vector<float> data_;
    size_t offset_ = 0; // consumed prefix; compacted lazily
};

} // namespace clearvoice
