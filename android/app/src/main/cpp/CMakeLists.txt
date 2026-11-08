# Builds libclearvoice_core.so for Android by reusing the shared core/
# directory (same sources as the Windows DLL).
cmake_minimum_required(VERSION 3.22.1)
project(clearvoice_android LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# repo root = android/app/src/main/cpp -> 5 levels up
get_filename_component(CV_REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../" ABSOLUTE)
set(CV_CORE_DIR "${CV_REPO_ROOT}/core")

# Shared core as a static lib (linked into our .so)
add_subdirectory("${CV_CORE_DIR}" "${CMAKE_CURRENT_BINARY_DIR}/clearvoice_core_build")

# The JNI library is what Kotlin loads as "clearvoice_core"
# (target name differs from core/CMakeLists.txt's own shared-lib target).
add_library(clearvoice_jni SHARED clearvoice_jni.cpp)
set_target_properties(clearvoice_jni PROPERTIES OUTPUT_NAME clearvoice_core)
target_include_directories(clearvoice_jni PRIVATE
    "${CV_CORE_DIR}/include"
    "${CV_CORE_DIR}/src"
)
target_link_libraries(clearvoice_jni PRIVATE clearvoice_core_static)
