#pragma once
/* Lock-free single-producer/single-consumer ring buffer of floats.
 *
 * Memory-ordering contract:
 *   - producer owns `head_`, publishes it with release after writing data
 *   - consumer owns `tail_`, publishes it with release after reading data
 *   - each side reads the other's index with acquire
 * Overflow policy: the producer never overwrites unread data; if the ring is
 * full, the NEWEST incoming samples are dropped and counted in overflow_.
 */
#include <atomic>
#include <cstddef>
#include <vector>

namespace clearvoice {

class RingBuffer {
public:
    explicit RingBuffer(size_t capacity);
    ~RingBuffer() = default;
    RingBuffer(const RingBuffer&) = delete;
    RingBuffer& operator=(const RingBuffer&) = delete;

    // Producer side (one thread only).
    size_t write(const float* src, size_t n); // returns samples actually written

    // Consumer side (one thread only).
    size_t read(float* dst, size_t n);              // returns samples actually read
    size_t readPadded(float* dst, size_t n);        // zero-fills shortfall, counts underflow

    size_t readable() const { return head_.load(std::memory_order_acquire) - tail_.load(std::memory_order_acquire); }
    size_t writable() const { return capacity_ - readable(); }
    size_t capacity() const { return capacity_; }

    unsigned long long overflowCount() const { return overflow_.load(std::memory_order_relaxed); }
    unsigned long long underflowCount() const { return underflow_.load(std::memory_order_relaxed); }

    void reset();

private:
    size_t capacity_;              // power of two
    size_t mask_;
    std::vector<float> buf_;
    std::atomic<size_t> head_{0};  // written by producer
    std::atomic<size_t> tail_{0};  // written by consumer
    std::atomic<unsigned long long> overflow_{0};
    std::atomic<unsigned long long> underflow_{0};
};

} // namespace clearvoice
