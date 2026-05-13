@echo off
REM PetGuard System Windows启动脚本 - 性能优化版

set PYTHONPATH=%PYTHONPATH%;%~dp0

if "%1"=="start" (
    echo 正在启动 PetGuard Web界面系统...
    start /B python app.py
    echo PetGuard Web界面系统已启动
    echo 访问 http://localhost:5000 查看系统界面
    goto :eof
)

if "%1"=="desktop" (
    echo 正在启动 PetGuard 桌面应用系统...
    start /B python main.py
    echo PetGuard 桌面应用系统已启动
    goto :eof
)

if "%1"=="stop" (
    echo 正在停止 PetGuard 系统...
    taskkill /IM python.exe /FI "WINDOWTITLE eq *app.py*" /F
    taskkill /IM python.exe /FI "WINDOWTITLE eq *main.py*" /F
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

if "%1"=="desktop-service" (
    echo 正在以后台服务方式启动 PetGuard 桌面版...
    python system_service.py --desktop
    goto :eof
)

echo.
echo ========================================
echo     PetGuard 智能安防系统
echo     性能优化版本启动脚本
echo ========================================
echo.
echo 用法: %0 [start^|desktop^|stop^|restart^|service^|desktop-service]
echo   start          - 启动PetGuard Web界面系统 (推荐)
echo   desktop        - 启动PetGuard 桌面应用系统
echo   stop           - 停止PetGuard系统
echo   restart        - 重启PetGuard系统
echo   service        - 以守护进程方式启动Web版PetGuard
echo   desktop-service - 以守护进程方式启动桌面版PetGuard
echo.
echo Web界面启动后，访问 http://localhost:5000 查看系统
echo ========================================