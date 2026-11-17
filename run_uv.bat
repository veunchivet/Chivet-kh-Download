@echo off
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul || (echo uv not found. Install: powershell -c "irm https://astral.sh/uv/install.ps1 | iex" & pause & exit /b 1)
if not exist .venv\Scripts\python.exe uv venv --python 3.12
uv pip install -r requirements.txt || (pause & exit /b 1)
start "" .venv\Scripts\pythonw.exe chivet_kh_download.py
