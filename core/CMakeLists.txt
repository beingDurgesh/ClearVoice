cmake_minimum_required(VERSION 3.16)
project(clearvoice_core VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(CV_BUILD_TESTS "Build core unit tests" ON)

# ---- vendored RNNoise (generic C path; pinned in third_party/PINNED.md) ----
set(RNNOISE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/third_party/rnnoise)
set(RNNOISE_SOURCES
    ${RNNOISE_DIR}/src/denoise.c
    ${RNNOISE_DIR}/src/celt_lpc.c
    ${RNNOISE_DIR}/src/kiss_fft.c
    ${RNNOISE_DIR}/src/nnet.c
    ${RNNOISE_DIR}/src/nnet_default.c
    ${RNNOISE_DIR}/src/parse_lpcnet_weights.c
    ${RNNOISE_DIR}/src/pitch.c
    ${RNNOISE_DIR}/src/rnn.c
    ${RNNOISE_DIR}/src/rnnoise_tables.c
    ${RNNOISE_DIR}/src/rnnoise_data.c
)
add_library(rnnoise STATIC ${RNNOISE_SOURCES})
target_include_directories(rnnoise PUBLIC ${RNNOISE_DIR}/include ${RNNOISE_DIR}/src)
if(MSVC)
    target_compile_definitions(rnnoise PRIVATE _CRT_SECURE_NO_WARNINGS)
    target_compile_options(rnnoise PRIVATE /W3 /wd4244 /wd4267 /wd4456 /wd4701)
else()
    target_compile_options(rnnoise PRIVATE -w)
endif()

# ---- ClearVoice core ----
set(CV_SOURCES
    src/ring_buffer.cpp
    src/frame_fifo.cpp
    src/resampler.cpp
    src/convert.cpp
    src/engine.cpp
    src/processor.cpp
    src/c_api.cpp
)

# Shared library: clearvoice_core.dll (Windows) / libclearvoice_core.so (Android)
add_library(clearvoice_core SHARED ${CV_SOURCES})
target_include_directories(clearvoice_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_definitions(clearvoice_core PRIVATE CV_BUILD_DLL)
target_link_libraries(clearvoice_core PRIVATE rnnoise)

# Static library for unit tests and for JNI (Android links this into the .so)
add_library(clearvoice_core_static STATIC ${CV_SOURCES})
target_include_directories(clearvoice_core_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_definitions(clearvoice_core_static PUBLIC CV_STATIC)
target_link_libraries(clearvoice_core_static PUBLIC rnnoise)

if(MSVC)
    foreach(t clearvoice_core clearvoice_core_static)
        target_compile_definitions(${t} PRIVATE _CRT_SECURE_NO_WARNINGS)
        target_compile_options(${t} PRIVATE /W3 /EHsc)
    endforeach()
else()
    target_compile_options(clearvoice_core PRIVATE -O2)
    target_compile_options(clearvoice_core_static PRIVATE -O2)
endif()

# ---- tests ----
if(CV_BUILD_TESTS)
    enable_testing()
    file(GLOB CV_TEST_SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/tests/*.cpp)
    add_executable(cv_tests ${CV_TEST_SOURCES})
    target_include_directories(cv_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_compile_definitions(cv_tests PRIVATE CV_STATIC)
    target_link_libraries(cv_tests PRIVATE clearvoice_core_static)
    if(NOT MSVC)
        target_compile_options(cv_tests PRIVATE -O2)
    endif()
    add_test(NAME cv_tests COMMAND cv_tests)
endif()

# Debug probe against upstream rnnoise directly (not part of the shipped lib)
option(CV_BUILD_PROBE "Build tools/debug_rnnoise.c probe" OFF)
if(CV_BUILD_PROBE)
    add_executable(debug_rnnoise ${CMAKE_CURRENT_SOURCE_DIR}/../tools/debug_rnnoise.c)
    target_include_directories(debug_rnnoise PRIVATE ${RNNOISE_DIR}/include ${RNNOISE_DIR}/src)
    target_link_libraries(debug_rnnoise PRIVATE rnnoise)
endif()
