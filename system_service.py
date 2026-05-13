import os
import sys
import signal
import time
import threading
import subprocess
from datetime import datetime
import logging
from pathlib import Path


class PetGuardService:
    def __init__(self):
        self.running = False
        self.process = None
        self.setup_logging()

    def setup_logging(self):
        """设置日志"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "service.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def start_web_server(self):
        """启动Web服务器"""
        try:
            # 确保依赖已安装
            cmd = [sys.executable, "app.py"]

            # 设置环境变量以优化性能
            env = os.environ.copy()
            env['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'  # 优化OpenCV性能
            env['PYTHONUNBUFFERED'] = '1'  # 不缓冲Python输出

            self.process = subprocess.Popen(cmd, env=env)
            self.logger.info("Web服务器已启动，PID: {}".format(self.process.pid))
            return True
        except Exception as e:
            self.logger.error(f"启动Web服务器失败: {e}")
            return False

    def start_desktop_app(self):
        """启动桌面应用程序"""
        try:
            cmd = [sys.executable, "main.py"]

            # 设置环境变量以优化性能
            env = os.environ.copy()
            env['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'  # 优化OpenCV性能
            env['PYTHONUNBUFFERED'] = '1'  # 不缓冲Python输出

            self.process = subprocess.Popen(cmd, env=env)
            self.logger.info("桌面应用程序已启动，PID: {}".format(self.process.pid))
            return True
        except Exception as e:
            self.logger.error(f"启动桌面应用程序失败: {e}")
            return False

    def monitor_process(self):
        """监控进程状态"""
        while self.running:
            if self.process and self.process.poll() is not None:
                self.logger.warning("应用程序意外退出，正在重启...")
                if '--desktop' in sys.argv:
                    self.start_desktop_app()
                else:
                    self.start_web_server()
            time.sleep(5)

    def start(self, app_type="web"):
        """启动服务"""
        if self.running:
            self.logger.warning("服务已在运行")
            return

        self.running = True
        self.logger.info("PetGuard服务正在启动...")

        if app_type == "desktop":
            success = self.start_desktop_app()
        else:
            success = self.start_web_server()

        if success:
            # 启动监控线程
            monitor_thread = threading.Thread(target=self.monitor_process)
            monitor_thread.daemon = True
            monitor_thread.start()

            self.logger.info(f"PetGuard {app_type} 服务已启动并运行")
        else:
            self.running = False
            self.logger.error("服务启动失败")

    def stop(self):
        """停止服务"""
        if not self.running:
            return

        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.logger.warning("应用程序强制终止")

        self.logger.info("PetGuard服务已停止")

    def run_daemon(self, app_type="web"):
        """作为守护进程运行"""
        def signal_handler(signum, frame):
            self.logger.info(f"收到信号 {signum}，正在关闭服务...")
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.start(app_type)

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()


if __name__ == "__main__":
    # 检查命令行参数决定运行类型
    app_type = "web"  # 默认运行web
    if len(sys.argv) > 1:
        if sys.argv[1] == "--desktop":
            app_type = "desktop"

    service = PetGuardService()
    service.run_daemon(app_type)