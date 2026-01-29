@echo off
echo Bezig met voorbereiden van de libs map...

:: 1. Verwijder de oude libs map en maak een nieuwe aan
if exist libs (
    rd /s /q libs
)
mkdir libs

:: 2. Installeer de libraries uit requirements.txt
echo Libraries installeren via pip...
pip install brdr==0.15.3 --target ./libs --no-compile --upgrade

:: 3. Verwijder metadata mappen (.dist-info en .egg-info)
echo Metadata opschonen...
for /d %%i in (libs\*.dist-info) do rd /s /q "%%i"
for /d %%i in (libs\*.egg-info) do rd /s /q "%%i"

:: 4. Verwijder alle __pycache__ mappen die diep in de structuur zitten
echo Pycache verwijderen...
for /d /r libs %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d"
)

echo.
echo Klaar! De 'libs' map is nu optimaal gevuld voor de QGIS Repository.
pause