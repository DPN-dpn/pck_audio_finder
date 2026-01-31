@echo off
REM Launch script: check for required libs and run installer if missing
setlocal
set "LIB1=%~dp0lib\HoyoAudioTools"
set "LIB2=%~dp0lib\vgmstream"
set "HAVE_LIBS=0"
if exist "%LIB1%\" if exist "%LIB2%\" (
	set "HAVE_LIBS=1"
)
if "%HAVE_LIBS%"=="1" (
	echo Required libraries found.
) else (
	echo Required libraries missing. Running installer...
	python "%~dp0source\util\lib_installer.py"
)

REM Launch the GUI application (uses source\main.py)
python "%~dp0source\main.py"
endlocal
