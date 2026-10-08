@echo off
rem ======================================================================
rem  CaseLocal starten. Doppelklick genügt; der Browser öffnet sich von selbst.
rem
rem  Prüft vorher, ob alles bereit ist (Einrichtung, Daten, Ollama, Modelle),
rem  und startet Ollama bei Bedarf automatisch.
rem ======================================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title CaseLocal
set "VPY=.venv\Scripts\python.exe"
set "PYTHONUTF8=1"
set "URL=http://localhost:8501"

rem --- Läuft CaseLocal schon? Dann nur den Browser öffnen -----------------
curl -s -o nul %URL%/_stcore/health && (
    start "" %URL%
    exit /b 0
)

rem --- Ist alles eingerichtet? -------------------------------------------
if not exist "%VPY%" (
    echo [Fehler] CaseLocal ist noch nicht eingerichtet. Bitte zuerst setup.bat ausführen.
    goto fehler
)
%VPY% -c "import config, sys; sys.exit(0 if config.SQLITE_PFAD.exists() else 1)" || (
    echo [Fehler] Es sind noch keine Urteile geladen. Bitte zuerst setup.bat ausführen.
    goto fehler
)
%VPY% -c "import config, sys; sys.exit(0 if (config.CHROMA_PFAD / 'chroma.sqlite3').exists() else 1)" || (
    echo [Fehler] Der Suchindex fehlt. Bitte zuerst setup.bat ausführen.
    goto fehler
)

rem --- Ollama und Modelle ------------------------------------------------
where ollama >nul 2>nul || (
    echo [Fehler] Ollama ist nicht installiert: https://ollama.com/download
    goto fehler
)
call :ollama_starten || goto fehler
for /f "delims=" %%m in ('%VPY% -c "import config; print(config.EMBED_MODELL); print(config.LLM_MODELL)"') do (
    ollama list | findstr /i /b /c:"%%m" >nul || (
        echo Das Modell %%m fehlt - lade es jetzt einmalig ...
        ollama pull %%m || goto fehler
    )
)

rem --- App starten -------------------------------------------------------
echo.
echo CaseLocal startet - der Browser öffnet sich gleich mit %URL%
echo Zum Beenden dieses Fenster schließen.
echo.
rem Im Hintergrund warten, bis die App antwortet, dann den Browser öffnen.
start "" /b cmd /c "for /l %%i in (1,1,60) do @(curl -s -o nul %URL%/_stcore/health && (start "" %URL% & exit) & ping -n 2 127.0.0.1 >nul)"
%VPY% -m streamlit run app.py --server.headless true --browser.gatherUsageStats false
exit /b 0

:fehler
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
