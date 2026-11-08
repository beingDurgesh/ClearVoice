@echo off
rem Package the ClearVoice Windows app into a single exe with PyInstaller.
cd "C:\Users\91862\Downloads\Noise Cancellation"
rmdir /s /q build\pyinstaller 2>nul
set PYTHONPATH=tools\pylibs
set QT_QPA_PLATFORM=offscreen
python -m PyInstaller --noconfirm --onedir --name ClearVoice ^
  --distpath build\dist --workpath build\pyinstaller --specpath build\pyinstaller ^
  --add-data "C:\Users\91862\Downloads\Noise Cancellation\build\core\Release\clearvoice_core.dll;." ^
  --paths windows ^
  --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets ^
  windows\main.py
exit /b %errorlevel%
