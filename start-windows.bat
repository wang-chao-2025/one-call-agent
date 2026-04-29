@echo off
setlocal enabledelayedexpansion

echo ====================================
echo Starting SuperBizAgent services
echo ====================================
echo.

REM Check uv package manager (optional, fallback to pip)
echo [1/8] Checking package manager...
where uv >nul 2>&1
if errorlevel 1 (
    echo [INFO] uv is not installed. Falling back to pip.
    echo [TIP] Install uv for faster setup: pip install uv
    set USE_UV=0
) else (
    echo [OK] uv detected.
    set USE_UV=1
)
echo.

REM Ensure Python version is compatible
echo [2/8] Configuring Python version...
if exist .python-version (
    set /p PYTHON_VERSION=<.python-version
    echo [INFO] Current configured version: !PYTHON_VERSION!

    REM Python 3.10 is incompatible
    echo !PYTHON_VERSION! | findstr /C:"3.10" >nul
    if not errorlevel 1 (
        echo [WARN] Python 3.10 is incompatible. Updating to 3.13...
        echo 3.13> .python-version
        echo [OK] Updated to Python 3.13
    )
) else (
    echo [INFO] Creating .python-version file...
    echo 3.13> .python-version
)
echo.

REM Create or sync virtual environment
echo [3/8] Preparing virtual environment...
if exist .venv\Scripts\python.exe (
    echo [INFO] Virtual environment exists. Checking updates...

    if "%USE_UV%"=="1" (
        uv sync 2>nul
        if errorlevel 1 (
            echo [WARN] uv sync failed. Using pip update...
            .venv\Scripts\python.exe -m pip install -e . -q
        ) else (
            echo [OK] uv sync completed.
        )
    ) else (
        echo [INFO] Updating dependencies with pip...
        .venv\Scripts\python.exe -m pip install -e . -q
    )
) else (
    echo [INFO] Creating new virtual environment...

    if "%USE_UV%"=="1" (
        echo [INFO] Trying uv sync first...
        uv sync 2>nul
        if not errorlevel 1 (
            echo [OK] Virtual environment created by uv.
            goto :venv_ready
        )
        echo [WARN] uv sync failed. Falling back to python -m venv...
    )

    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        echo [TIP] Please make sure Python 3.11+ is installed.
        pause
        exit /b 1
    )

    echo [INFO] Installing project dependencies. This may take a few minutes...
    .venv\Scripts\python.exe -m pip install --upgrade pip -q
    .venv\Scripts\python.exe -m pip install -e . -q
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
)

:venv_ready
echo [OK] Virtual environment is ready.
echo.

REM Set Python command
set PYTHON_CMD=.venv\Scripts\python.exe

REM Start Docker Compose
echo [4/8] Starting Milvus vector database...
docker ps --format "{{.Names}}" | findstr "milvus-standalone" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Milvus container is already running.
) else (
    docker compose -f vector-database.yml up -d
    if errorlevel 1 (
        echo [ERROR] Docker failed to start. Please start Docker Desktop first.
        pause
        exit /b 1
    )
    echo [INFO] Waiting for Milvus to initialize 10s...
    timeout /t 10 /nobreak >nul
)
echo [OK] Milvus is ready.
echo.

REM Start CLS MCP server
echo [5/8] Starting CLS MCP server...
start "CLS MCP Server" /min %PYTHON_CMD% mcp_servers/cls_server.py
timeout /t 2 /nobreak >nul
echo [OK] CLS MCP server started.
echo.

REM Start Monitor MCP server
echo [6/8] Starting Monitor MCP server...
start "Monitor MCP Server" /min %PYTHON_CMD% mcp_servers/monitor_server.py
timeout /t 2 /nobreak >nul
echo [OK] Monitor MCP server started.
echo.

REM Start FastAPI server
echo [7/8] Starting FastAPI server...
start "SuperBizAgent API" %PYTHON_CMD% -m uvicorn app.main:app --host 0.0.0.0 --port 9900
echo [INFO] Waiting for API startup (15s)...
timeout /t 15 /nobreak >nul
echo.

REM Check health and upload documents
echo [8/8] Checking service health...
curl -s http://localhost:9900/health >nul 2>&1
if errorlevel 1 (
    echo [WARN] API may still be starting. Please wait a little longer.
) else (
    echo [OK] FastAPI is healthy.
    echo.

    if exist aiops-docs\*.md (
        echo [INFO] Uploading markdown documents to vector database...
        for %%f in (aiops-docs\*.md) do (
            echo   Uploading: %%~nxf
            curl -s -X POST http://localhost:9900/api/upload -F "file=@%%f" >nul 2>&1
        )
        echo [OK] Document upload completed.
    ) else (
        echo [INFO] No markdown files found in aiops-docs. Skipping upload.
    )
)

echo.
echo ====================================
echo All services started.
echo ====================================
echo Web UI: http://localhost:9900
echo API Docs: http://localhost:9900/docs
echo.
echo Logs:
echo   - FastAPI: logs\app_*.log (rotates daily with Loguru)
echo   - CLS MCP: type mcp_cls.log
echo   - Monitor: type mcp_monitor.log
echo Stop services: stop-windows.bat
echo ====================================
pause
