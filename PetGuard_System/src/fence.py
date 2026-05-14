# src/fence.py 完整参考
import cv2
import numpy as np

class VirtualFence:
    def __init__(self, polygon_coords):
        # 确保坐标是 np.array 格式
        self.polygon = np.array(polygon_coords, dtype=np.int32)

    def is_intruding(self, point):
        """
        使用 OpenCV 的多边形测试函数
        返回值 >= 0 表示点在多边形内部或边缘
        """
        # point 为 (x, y)
        result = cv2.pointPolygonTest(self.polygon, point, False)
        return result >= 0

    def draw_fence(self, frame, is_alert=False):
        color = (0, 0, 255) if is_alert else (0, 255, 0)
        # 画出闭合的多边形
        cv2.polylines(frame, [self.polygon], isClosed=True, color=color, thickness=2)
        # 填充半透明颜色增强视觉效果
        overlay = frame.copy()
        cv2.fillPoly(overlay, [self.polygon], color)
        return cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)