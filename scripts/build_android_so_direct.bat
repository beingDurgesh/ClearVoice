@echo off
rem Compile libclearvoice_core.so for Android ABIs directly with NDK clang.
rem .c files (rnnoise) compiled as C, .cpp as C++, then linked into one .so.
cd "C:\Users\91862\Downloads\Noise Cancellation"
set NDK=tools\android-sdk\ndk\27.3.13750724
set PREBUILT=%NDK%\toolchains\llvm\prebuilt\windows-x86_64
set SYSROOT=%PREBUILT%\sysroot
set CLANG=%PREBUILT%\bin\clang.exe
set CLANGXX=%PREBUILT%\bin\clang++.exe
set NM=%PREBUILT%\bin\llvm-nm.exe
set JDK=C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot

rem JNI headers in a space-free dir (cmd quoting + sandbox)
mkdir tools\jni-include 2>nul
copy /y "%JDK%\include\jni.h" tools\jni-include\ >nul
if not exist tools\jni-include\jni_md.h copy /y tools\jni-include\jni_md.h tools\jni-include\jni_md.h >nul

set INC=-Icore\include -Icore\third_party\rnnoise\include -Icore\third_party\rnnoise\src -Itools\jni-include
set RN=core\third_party\rnnoise\src\denoise.c core\third_party\rnnoise\src\celt_lpc.c core\third_party\rnnoise\src\kiss_fft.c core\third_party\rnnoise\src\nnet.c core\third_party\rnnoise\src\nnet_default.c core\third_party\rnnoise\src\parse_lpcnet_weights.c core\third_party\rnnoise\src\pitch.c core\third_party\rnnoise\src\rnn.c core\third_party\rnnoise\src\rnnoise_tables.c core\third_party\rnnoise\src\rnnoise_data.c
set CPPSRC=core\src\ring_buffer.cpp core\src\frame_fifo.cpp core\src\resampler.cpp core\src\convert.cpp core\src\engine.cpp core\src\processor.cpp core\src\c_api.cpp android\app\src\main\cpp\clearvoice_jni.cpp

mkdir build\android-so 2>nul

call :build arm64-v8a aarch64-linux-android24
if errorlevel 1 exit /b 1
call :build x86_64 x86_64-linux-android24
if errorlevel 1 exit /b 1

%NM% -D --defined-only build\android-so\libclearvoice_core-arm64-v8a.so | find /c "Java_com_clearvoice"
echo DONE
exit /b 0

:build
set ABI=%1
set TARGET=%2
set OBJDIR=build\android-so\obj-%ABI%
if not exist %OBJDIR% mkdir %OBJDIR%
echo === %ABI% (%TARGET%) ===
for %%F in (%RN%) do %CLANG% --target=%TARGET% --sysroot=%SYSROOT% -O2 -fPIC -w %INC% -c %%F -o %OBJDIR%\%%~nF.o || exit /b 1
for %%F in (%CPPSRC%) do %CLANGXX% --target=%TARGET% --sysroot=%SYSROOT% -O2 -fPIC -std=c++17 -w %INC% -c %%F -o %OBJDIR%\%%~nF.o || exit /b 1
%CLANGXX% --target=%TARGET% --sysroot=%SYSROOT% -shared -o build\android-so\libclearvoice_core-%ABI%.so %OBJDIR%\*.o || exit /b 1
echo %ABI% BUILD OK
exit /b 0
