@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 goto failed

if exist ".venv\Scripts\python.exe" goto install
where py.exe >nul 2>nul
if errorlevel 1 goto use_python
py -3 -m venv ".venv"
if errorlevel 1 goto failed
goto install

:use_python
python -m venv ".venv"
if errorlevel 1 goto failed

:install
".venv\Scripts\python.exe" -c "from PyQt5.QtWidgets import QApplication" >nul 2>nul
if not errorlevel 1 goto launch
echo Installing the desktop pet dependency for the first launch...
".venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 goto failed

:launch
start "" ".venv\Scripts\pythonw.exe" "pet.py"
if errorlevel 1 goto failed
popd
exit /b 0

:failed
echo.
echo Could not start. Check the error above and confirm Python and internet access are available.
pause
exit /b 1
