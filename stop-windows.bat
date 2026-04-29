@echo off
setlocal

echo ====================================
echo Stopping SuperBizAgent services
echo ====================================
echo.

REM Stop FastAPI service
echo [1/4] Stopping FastAPI service...
taskkill /FI "WINDOWTITLE eq SuperBizAgent API*" /F >nul 2>&1
if errorlevel 1 (
    echo [INFO] FastAPI service is not running.
) else (
    echo [OK] FastAPI service stopped.
)
echo.

REM Stop CLS MCP service
echo [2/4] Stopping CLS MCP service...
taskkill /FI "WINDOWTITLE eq CLS MCP Server*" /F >nul 2>&1
if errorlevel 1 (
    echo [INFO] CLS MCP service is not running.
) else (
    echo [OK] CLS MCP service stopped.
)
echo.

REM Stop Monitor MCP service
echo [3/4] Stopping Monitor MCP service...
taskkill /FI "WINDOWTITLE eq Monitor MCP Server*" /F >nul 2>&1
if errorlevel 1 (
    echo [INFO] Monitor MCP service is not running.
) else (
    echo [OK] Monitor MCP service stopped.
)
echo.

REM Stop Milvus container
echo [4/4] Stopping Milvus container...
docker ps --format "{{.Names}}" | findstr /I "milvus" >nul 2>&1
if not errorlevel 1 (
    docker compose -f vector-database.yml down
    if errorlevel 1 (
        echo [ERROR] Failed to stop Docker container.
    ) else (
        echo [OK] Milvus container stopped.
    )
) else (
    echo [INFO] Milvus container is not running.
)
echo.

echo ====================================
echo All services stopped.
echo ====================================
echo.
echo Tip:
echo   - To remove Docker volumes too, run:
echo     docker compose -f vector-database.yml down -v
echo.
pause
