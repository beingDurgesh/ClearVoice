#pragma once
/* Minimal test framework: TEST(name) registers a case, CHECK throws on failure,
 * cvtest::runAll() executes everything and returns the process exit code. */
#include <cmath>
#include <cstdio>
#include <functional>
#include <string>
#include <vector>

namespace cvtest {

struct Case {
    std::string name;
    std::function<void()> fn;
};

inline std::vector<Case>& registry() {
    static std::vector<Case> r;
    return r;
}

struct Registrar {
    Registrar(std::string name, std::function<void()> fn) {
        registry().push_back({std::move(name), std::move(fn)});
    }
};

struct Failure {
    std::string msg;
};

inline void check(bool cond, const char* expr, const char* file, int line) {
    if (!cond) {
        char buf[512];
        std::snprintf(buf, sizeof buf, "%s:%d: CHECK failed: %s", file, line, expr);
        throw Failure{buf};
    }
}

inline int runAll() {
    int failed = 0;
    for (auto& c : registry()) {
        try {
            c.fn();
            std::printf("[PASS] %s\n", c.name.c_str());
        } catch (const Failure& f) {
            std::printf("[FAIL] %s\n       %s\n", c.name.c_str(), f.msg.c_str());
            ++failed;
        } catch (const std::exception& e) {
            std::printf("[FAIL] %s\n       exception: %s\n", c.name.c_str(), e.what());
            ++failed;
        } catch (...) {
            std::printf("[FAIL] %s\n       unknown exception\n", c.name.c_str());
            ++failed;
        }
    }
    std::printf("----\n%zu tests, %d failed\n", registry().size(), failed);
    return failed ? 1 : 0;
}

} // namespace cvtest

#define TEST(name)                                            \
    static void name();                                       \
    static cvtest::Registrar reg_##name(#name, name);         \
    static void name()

#define CHECK(cond) cvtest::check(static_cast<bool>(cond), #cond, __FILE__, __LINE__)
#define CHECK_NEAR(a, b, tol) \
    cvtest::check(std::fabs(static_cast<double>(a) - static_cast<double>(b)) <= (tol), #a " ~= " #b, __FILE__, __LINE__)
