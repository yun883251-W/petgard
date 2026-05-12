import sys
import os
import cv2
import json
import time
from collections import Counter, deque

# 自动修复路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from src.detector import PetDetector
from src.fence import VirtualFence
from src.alerts import AlertManager


def main(source_path):
    # 1. 加载配置
    config_path = os.path.join(current_dir, 'config', 'roi_config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 2. 初始化组件
    detector = PetDetector('models/yolov8s.pt')
    fence = VirtualFence(config['polygon'])
    alert_mgr = AlertManager()

    cap = cv2.VideoCapture(int(source_path) if source_path.isdigit() else source_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if 1 < fps < 120 else 20.0

    # 状态管理
    active_writers = {}
    last_seen_in_fence = {}

    # --- 亮点功能：类别平滑存储 ---
    # 记录每个 ID 最近 10 帧的类别，防止猫狗混淆
    id_class_history = {}

    CLOSE_DELAY = 2.0

    print(f"🚀 系统已启动。当前模式：猫狗分类平滑优化版")

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success: break

            results = detector.track(frame, conf=0.4)  # 提高阈值
            annotated_frame = frame.copy()
            curr_ts = time.time()
            intruder_ids = set()

            if results.boxes is not None and results.boxes.id is not None:
                boxes = results.boxes.xyxy.cpu().numpy()
                track_ids = results.boxes.id.int().cpu().numpy()
                cls_ids = results.boxes.cls.int().cpu().numpy()

                for box, tid, cid in zip(boxes, track_ids, cls_ids):
                    # --- 投票逻辑开始 ---
                    if tid not in id_class_history:
                        id_class_history[tid] = deque(maxlen=10)
                    id_class_history[tid].append(cid)

                    # 取出现次数最多的类别作为稳定类别
                    stable_cls = Counter(id_class_history[tid]).most_common(1)[0][0]
                    label_name = "Cat" if stable_cls == 15 else "Dog"
                    # --- 投票逻辑结束 ---

                    # 判定逻辑
                    foot_point = (int((box[0] + box[2]) / 2), int(box[3]))
                    if fence.is_intruding(foot_point):
                        intruder_ids.add(tid)
                        last_seen_in_fence[tid] = curr_ts

                        if tid not in active_writers:
                            writer, _ = alert_mgr.create_video_writer(frame, tid, fps)
                            active_writers[tid] = writer
                            print(f"🚨 [警报] {label_name} (ID:{tid}) 闯入禁区！")

                    # 在画面上画出稳定后的标签
                    color = (0, 0, 255) if tid in intruder_ids else (0, 255, 0)
                    cv2.rectangle(annotated_frame, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), color, 2)
                    cv2.putText(annotated_frame, f"{label_name} #{tid}", (int(box[0]), int(box[1]) - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # 延迟关闭逻辑
            for tid in list(active_writers.keys()):
                if tid in intruder_ids or (curr_ts - last_seen_in_fence.get(tid, 0) < CLOSE_DELAY):
                    active_writers[tid].write(annotated_frame)
                else:
                    active_writers[tid].release()
                    del active_writers[tid]
                    print(f"✅ ID:{tid} 离开，视频已存档。")

            # 绘制围栏
            annotated_frame = fence.draw_fence(annotated_frame, is_alert=len(intruder_ids) > 0)
            cv2.imshow("PetGuard AI", annotated_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'): break

    finally:
        for w in active_writers.values(): w.release()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    test_video = os.path.join(current_dir, "data", "samples", "test_video.mp4")
    main(test_video)