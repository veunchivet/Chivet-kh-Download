@echo off
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
set "VER=1.9.2"
echo Closing Chivet-kh Download if it is running (the build cannot replace a running exe) ...
taskkill /F /IM ChivetKhDownload.exe >nul 2>nul
timeout /t 2 /nobreak >nul
if exist .venv\Scripts\python.exe (
  uv pip install -U -r requirements.txt pyinstaller
  set "PY=.venv\Scripts\python.exe"
) else (
  python -m pip install -U -r requirements.txt pyinstaller
  set "PY=python"
)
%PY% -c "import yt_dlp; print('yt-dlp in this build:', yt_dlp.version.__version__)"
%PY% -m PyInstaller --noconfirm --windowed --name ChivetKhDownload --icon app_icon.ico --collect-all yt_dlp --collect-all yt_dlp_ejs --collect-all imageio_ffmpeg chivet_kh_download.py
if errorlevel 1 (echo Build failed & pause & exit /b 1)
xcopy /E /I /Y browser_extension dist\ChivetKhDownload\browser_extension >nul
copy /Y README.md dist\ChivetKhDownload\ >nul
echo.
echo Creating the release zip (exe + _internal + browser_extension) ...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\ChivetKhDownload' -DestinationPath 'dist\ChivetKhDownload-%VER%-win64.zip' -Force"
echo.
echo Done!
echo   App      : dist\ChivetKhDownload\ChivetKhDownload.exe
echo   Release  : dist\ChivetKhDownload-%VER%-win64.zip   ^<-- upload THIS file to GitHub Releases
pause
