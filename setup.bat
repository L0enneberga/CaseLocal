@echo off
rem ======================================================================
rem  CaseLocal - Ersteinrichtung. Doppelklick genügt.
rem
rem  Legt die virtuelle Umgebung an, installiert die Bibliotheken, lädt die
rem  Modelle und die Urteile und baut den Suchindex - alles in einem Durchgang.
rem  Kann gefahrlos mehrfach ausgeführt werden: Erledigtes wird übersprungen.
rem ======================================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title CaseLocal - Einrichtung
set "VPY=.venv\Scripts\python.exe"
set "PYTHONUTF8=1"

echo.
echo === CaseLocal: Ersteinrichtung ===
echo.

rem --- Python finden (bevorzugt über den Python-Launcher "py") ------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY (
    echo [Fehler] Python wurde nicht gefunden. Installieren von https://www.python.org/downloads/
    echo          und im Installer "Add python.exe to PATH" ankreuzen.
    goto fehler
)
%PY% -c "import sys; sys.exit(sys.version_info < (3, 11))" || (
    echo [Fehler] Python 3.11 oder neuer wird benötigt.
    goto fehler
)

rem --- 1. Virtuelle Umgebung --------------------------------------------
if exist "%VPY%" (
    echo [1/7] Virtuelle Umgebung .venv ist schon vorhanden.
) else (
    echo [1/7] Lege die virtuelle Umgebung .venv an ...
    %PY% -m venv .venv || goto fehler
)

rem --- 2. Bibliotheken ---------------------------------------------------
echo [2/7] Installiere die Bibliotheken - beim ersten Mal dauert das einige Minuten ...
%VPY% -m pip install -q --disable-pip-version-check -r requirements.txt || goto fehler

rem --- 3. Ollama und Modelle ---------------------------------------------
echo [3/7] Prüfe Ollama und lade die Modelle aus config.py ...
where ollama >nul 2>nul || (
    echo [Fehler] Ollama ist nicht installiert: https://ollama.com/download
    goto fehler
)
call :ollama_starten || goto fehler
for /f "delims=" %%m in ('%VPY% -c "import config; print(config.EMBED_MODELL); print(config.LLM_MODELL)"') do (
    echo        Modell %%m ...
    ollama pull %%m || goto fehler
)

rem --- 4. Zugang zum Datensatz auf Hugging Face --------------------------
echo [4/7] Prüfe den Hugging-Face-Zugang ...
.venv\Scripts\hf.exe auth whoami >nul 2>nul || (
    echo        Du bist noch nicht bei Hugging Face angemeldet. Vorher einmalig:
    echo         1. Auf https://huggingface.co/datasets/openlegaldata/court-decisions-germany
    echo            die Zugangsbedingungen akzeptieren.
    echo         2. Unter https://huggingface.co/settings/tokens einen Token "Read" erstellen.
    echo        Den Token gleich einfügen - Rechtsklick, die Eingabe bleibt unsichtbar.
    echo        Die Frage nach "git credential" mit n beantworten.
    .venv\Scripts\hf.exe auth login || goto fehler
)

rem --- 5. bis 7. Daten laden, Suchindex bauen, Gesetze laden ----------------------------
echo [5/7] Wähle und lade die Urteile - beim ersten Mal ca. 3 GB, das dauert eine Weile ...
%VPY% daten_laden.py || goto fehler
echo [6/7] Baue den Suchindex - bei 10.000 Urteilen etwa 2 bis 3 Stunden, abbrechen und fortsetzen geht ...
%VPY% index_bauen.py || goto fehler
echo [7/7] Lade die 100 meistzitierten Bundesgesetze von gesetze-im-internet.de - beim erneuten Start nur geänderte ...
%VPY% gesetze_laden.py || goto fehler

rem --- Optional: KI-Schlagworte ------------------------------------------
echo.
choice /c JN /m "Optional: KI-Schlagworte für 100 Urteile vergeben? Dauert einige Minuten."
if errorlevel 2 goto fertig
%VPY% schlagworte.py --anzahl 100 || goto fehler

:fertig
echo.
echo === Einrichtung abgeschlossen. Starten mit Doppelklick auf start.bat ===
echo.
pause
exit /b 0

:fehler
echo.
echo Einrichtung abgebrochen - die Meldung oben erklärt, was fehlt.
echo Nach dem Beheben setup.bat einfach erneut starten. Erledigtes wird übersprungen.
echo.
pause
exit /b 1

:ollama_starten
rem Prüft, ob Ollama läuft, und startet es sonst (bis zu 30 Sekunden warten).
curl -s -o nul http://localhost:11434/api/tags && exit /b 0
echo        Ollama läuft nicht - starte es ...
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" (
    start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
) else (
    start "Ollama" /min ollama serve
)
for /l %%i in (1,1,30) do (
    ping -n 2 127.0.0.1 >nul
    curl -s -o nul http://localhost:11434/api/tags && exit /b 0
)
echo [Fehler] Ollama ließ sich nicht starten. Bitte die Ollama-App von Hand starten.
exit /b 1
