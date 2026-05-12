# src/alerts.py 优化版本 - 只保留图片功能

import cv2
import os
import csv
from datetime import datetime
import numpy as np


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

    def capture_intrusion_alert(self, frame, track_id):
        """抓拍图片作为闯入警报记录"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_filename = f"intruder_{track_id}_{timestamp}.jpg"
        full_image_path = os.path.join(self.image_path, image_filename)

        # 保存图片
        cv2.imwrite(full_image_path, frame)

        # 记录日志（不再记录视频文件，只记录图片）
        with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                track_id,
                image_filename,
                "Alert Triggered"
            ])

        return full_image_path

    def capture_snapshot(self, frame, track_id):
        """额外的图片抓拍方法"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshot_{track_id}_{timestamp}.jpg"
        full_path = os.path.join(self.image_path, filename)
        cv2.imwrite(full_path, frame)
        return full_path