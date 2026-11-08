@echo off
subst X: "C:\Users\91862\Downloads\Noise Cancellation"
if errorlevel 1 ( echo SUBST FAILED & exit /b 1 )
echo SUBST OK
dir X:\ >nul 2>&1 && echo DIR OK || echo DIR FAILED
subst
