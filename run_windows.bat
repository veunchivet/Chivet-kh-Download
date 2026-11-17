@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
start "" pythonw chivet_kh_download.py
