# src/alerts.py 优化版本 - 异步图片抓拍功能

import cv2
import os
import csv
from datetime import datetime
import numpy as np
import threading
import queue
from typing import Dict, Tuple


class AsyncAlertLogger:
    """异步警报记录器 — 在后台线程统一处理图片保存和CSV日志写入，不阻塞主帧循环"""
    def __init__(self, log_file, max_queue_size=20):
        self.log_file = log_file
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def _worker(self):
        """后台工作线程：顺序处理队列中的保存+日志任务"""
        while self.running:
            try:
                task = self.queue.get(timeout=1)
                if task is None:  # 停止信号
                    break

                frame, filepath, csv_row = task
                try:
                    # 1. 保存图片
                    cv2.imwrite(filepath, frame)
                    # 2. 写入CSV日志
                    if csv_row and self.log_file:
                        with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
                            csv.writer(f).writerow(csv_row)
                except Exception as e:
                    print(f"❌ [异步保存错误] {str(e)}")

                self.queue.task_done()
            except queue.Empty:
                continue

    def save(self, frame, filepath, csv_row=None):
        """异步保存图片并记录日志（非阻塞）"""
        try:
            self.queue.put((frame, filepath, csv_row), block=False)
        except queue.Full:
            print("⚠️ [队列满] 丢弃抓拍任务以避免阻塞")

    def stop(self):
        """停止后台工作线程"""
        self.running = False
        self.worker_thread.join(timeout=3)


class AlertManager:
    def __init__(self, base_path="data"):
        self.image_path = os.path.join(base_path, "images")  # 只保留图片存储路径
        self.log_path = os.path.join(base_path, "logs")

        os.makedirs(self.image_path, exist_ok=True)  # 创建图片目录
        os.makedirs(self.log_path, exist_ok=True)

        self.log_file = os.path.join(self.log_path, "intrusion_history.csv")
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Pet_ID", "Image_File", "Status"])
        else:
            # 确保已有 CSV 文件包含表头
            with open(self.log_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
            if first_line and "Time" not in first_line:
                # 缺少表头，补上
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    existing = f.read()
                with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
                    f.write("Time,Pet_ID,Image_File,Status\n")
                    f.write(existing)

        # 创建异步日志记录器（同时处理图片保存和CSV写入）
        self.async_logger = AsyncAlertLogger(self.log_file, max_queue_size=20)

    def capture_intrusion_alert(self, frame, track_id):
        """完全异步的抓拍 — 图片保存和日志写入均在后台线程处理"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_filename = f"intruder_{track_id}_{timestamp}.jpg"
        full_image_path = os.path.join(self.image_path, image_filename)

        csv_row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(track_id),
            image_filename,
            "Alert Triggered"
        ]

        # 将图片和日志一并放入后台队列，主线程零阻塞
        self.async_logger.save(frame, full_image_path, csv_row)
        return full_image_path

    def capture_snapshot(self, frame, track_id):
        """异步额外抓拍"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshot_{track_id}_{timestamp}.jpg"
        full_path = os.path.join(self.image_path, filename)
        self.async_logger.save(frame, full_path)
        return full_path

    def shutdown(self):
        """关闭异步记录器"""
        self.async_logger.stop()