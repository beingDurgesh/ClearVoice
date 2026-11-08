@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
cd "C:\Users\91862\Downloads\Noise Cancellation"
set JDK=C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot
rem vcvars does not stick in this sandbox; set LIB/INCLUDE explicitly
set "LIB=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207\lib\x64;C:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0\um\x64;C:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0\ucrt\x64"
set "INCLUDE=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207\include;C:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0\ucrt;C:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0\um;C:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0\shared"
mkdir tools\jni_host_test\classes 2>nul
cl /EHsc /LD /O2 /std:c++17 /MT /DCV_STATIC ^
  /I"%JDK%\include" /I"%JDK%\include\win32" ^
  /Icore\include /Iandroid\app\src\main\cpp ^
  android\app\src\main\cpp\clearvoice_jni.cpp ^
  build\core-mt\Release\clearvoice_core_static.lib build\core-mt\Release\rnnoise.lib ^
  /Fe:tools\jni_host_test\clearvoice_jni_host.dll
set BUILD=%errorlevel%
if %BUILD% neq 0 exit /b %BUILD%
"%JDK%\bin\javac.exe" -d tools\jni_host_test\classes tools\jni_host_test\ClearVoiceEngine.java
exit /b %errorlevel%
