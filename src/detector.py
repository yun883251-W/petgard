# src/detector.py

from ultralytics import YOLO

class PetDetector:
    def __init__(self, model_path='models/yolov8s.pt'):
        # 建议默认使用 s 版，兼顾速度与精度
        self.model = YOLO(model_path)

    def track(
        self,
        frame,
        conf=0.3,
        imgsz=640,
        classes=None,
        iou=0.5,
        tracker="bytetrack.yaml",
        device=None,
        half=False,
    ):
        """
        执行目标追踪，并仅过滤出猫(15)和狗(16)
        """
        kwargs = {
            "source": frame,
            "imgsz": imgsz,
            "persist": True,
            "conf": conf,
            "iou": iou,
            "classes": classes or [15, 16],
            "tracker": tracker,
            "verbose": False,
        }
        if device is not None:
            kwargs["device"] = device
        if half:
            kwargs["half"] = True

        results = self.model.track(**kwargs)
        return results[0]
