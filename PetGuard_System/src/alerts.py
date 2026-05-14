# src/alerts.py 完整修改版

import cv2
import os
import csv
from datetime import datetime


class AlertManager:
    def __init__(self, base_path="data"):
        self.video_path = os.path.join(base_path, "videos")
        self.log_path = os.path.join(base_path, "logs")
        os.makedirs(self.video_path, exist_ok=True)
        os.makedirs(self.log_path, exist_ok=True)

        self.log_file = os.path.join(self.log_path, "intrusion_history.csv")
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Pet_ID", "Video_File", "Status"])

    def create_video_writer(self, frame, track_id, fps=20.0):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"intruder_{track_id}_{timestamp}.mp4"
        full_path = os.path.join(self.video_path, filename)

        # --- 重点：修改编码器以适配 Chrome ---
        # 'avc1' 是 H.264 编码，Chrome 完美支持
        # 如果运行报错，请尝试替换为 'H264' 或 'XVID'
        fourcc = cv2.VideoWriter_fourcc(*'avc1')

        height, width = frame.shape[:2]
        writer = cv2.VideoWriter(full_path, fourcc, fps, (width, height))

        # 记录日志
        with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                track_id,
                filename,
                "Recorded"
            ])

        return writer, full_path