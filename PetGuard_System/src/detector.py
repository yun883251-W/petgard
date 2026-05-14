# src/detector.py

from ultralytics import YOLO

class PetDetector:
    def __init__(self, model_path='models/yolov8s.pt'):
        # 建议默认使用 s 版，兼顾速度与精度
        self.model = YOLO(model_path)

    def track(self, frame, conf=0.3):
        """
        执行目标追踪，并仅过滤出猫(15)和狗(16)
        """
        results = self.model.track(
            frame,
            imgsz=640,
            persist=True,
            conf=conf,
            # 关键修改：只允许识别 COCO 数据集中的猫和狗
            classes=[15, 16],
            tracker="bytetrack.yaml",
            verbose=False
        )
        return results[0]