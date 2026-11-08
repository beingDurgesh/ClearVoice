@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
cd "C:\Users\91862\Downloads\Noise Cancellation"
cl /O2 /I core\third_party\rnnoise\include /I core\third_party\rnnoise\src tools\debug_rnnoise.c build\core\Release\rnnoise.lib /Fe:tools\debug_rnnoise.exe
exit /b %errorlevel%
