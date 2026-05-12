@echo off
REM PetGuard System Windows启动脚本

set PYTHONPATH=%PYTHONPATH%;%~dp0

if "%1"=="start" (
    echo 正在启动 PetGuard 系统...
    start /B python app.py
    echo PetGuard 系统已启动
    goto :eof
)

if "%1"=="stop" (
    echo 正在停止 PetGuard 系统...
    taskkill /IM python.exe /FI "WINDOWTITLE eq *app.py*" /F
    echo PetGuard 系统已停止
    goto :eof
)

if "%1"=="restart" (
    call %0 stop
    timeout /t 2 /nobreak >nul
    call %0 start
    goto :eof
)

if "%1"=="service" (
    echo 正在以后台服务方式启动 PetGuard...
    python system_service.py
    goto :eof
)

echo 用法: %0 [start^|stop^|restart^|service]
echo   start  - 启动PetGuard系统
echo   stop   - 停止PetGuard系统
echo   restart - 重启PetGuard系统
echo   service - 以守护进程方式启动PetGuard