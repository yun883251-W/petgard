#!/bin/bash
# PetGuard System 启动脚本

# 设置环境变量
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

case "$1" in
    start)
        echo "正在启动 PetGuard 系统..."
        python app.py &
        echo $! > petguard.pid
        echo "PetGuard 系统已启动，PID: $(cat petguard.pid)"
        ;;
    stop)
        if [ -f petguard.pid ]; then
            PID=$(cat petguard.pid)
            kill $PID
            rm petguard.pid
            echo "PetGuard 系统已停止"
        else
            echo "PetGuard 系统未运行"
        fi
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    status)
        if [ -f petguard.pid ]; then
            PID=$(cat petguard.pid)
            if ps -p $PID > /dev/null; then
                echo "PetGuard 系统正在运行，PID: $PID"
            else
                echo "PetGuard 系统未运行，但 PID 文件存在"
            fi
        else
            echo "PetGuard 系统未运行"
        fi
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac