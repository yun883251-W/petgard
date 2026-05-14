import os
import sys
import cv2
import time
import json
import csv
from flask import Flask, render_template, Response, jsonify, send_from_directory

# 路径修复
root_path = os.path.dirname(os.path.abspath(__file__))
if root_path not in sys.path:
    sys.path.append(root_path)

from src.detector import PetDetector
from src.fence import VirtualFence
from src.alerts import AlertManager  # 必须导入录像管理器

app = Flask(__name__)

# --- 配置 ---
VIDEO_SOURCE = os.path.join(root_path, "data", "samples", "test_video.mp4")
CONFIG_FILE = os.path.join(root_path, "config", "roi_config.json")

detector = PetDetector('models/yolov8s.pt')
alert_mgr = AlertManager()  # 初始化录像管理器
with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    config = json.load(f)
fence = VirtualFence(config['polygon'])

latest_status = {"intruder_count": 0, "status_text": "系统运行中", "last_update": ""}
active_writers = {}  # 存放正在录像的句柄 {track_id: writer}
last_seen_time = {}  # 存放目标最后出现时间，用于延迟关闭


def generate_frames():
    global latest_status
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0

    while True:
        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        curr_ts = time.time()
        results = detector.track(frame, conf=0.4)
        annotated_frame = results.plot()

        current_intruder_ids = set()
        if results.boxes is not None and results.boxes.id is not None:
            boxes = results.boxes.xyxy.cpu().numpy()
            track_ids = results.boxes.id.int().cpu().numpy()

            for box, tid in zip(boxes, track_ids):
                foot_point = (int((box[0] + box[2]) / 2), int(box[3]))

                # --- 核心修复：触发录像逻辑 ---
                if fence.is_intruding(foot_point):
                    current_intruder_ids.add(tid)
                    last_seen_time[tid] = curr_ts

                    # 如果该目标还没开始录像，创建一个新的 Writer
                    if tid not in active_writers:
                        writer, _ = alert_mgr.create_video_writer(frame, tid, fps)
                        active_writers[tid] = writer
                        print(f"🚨 [录制中] 目标 ID:{tid} 进入禁区")

        # --- 管理所有活动的录像句柄 ---
        for tid in list(active_writers.keys()):
            # 如果目标还在禁区，或者在 2 秒缓冲时间内，继续写入
            if tid in current_intruder_ids or (curr_ts - last_seen_time.get(tid, 0) < 2.0):
                active_writers[tid].write(annotated_frame)
            else:
                # 超过 2 秒没出现，关闭录像
                active_writers[tid].release()
                del active_writers[tid]
                print(f"✅ [已保存] ID:{tid} 录像结束")

        # 更新 Web 状态
        latest_status["intruder_count"] = len(current_intruder_ids)
        latest_status["status_text"] = "🚨 发现违规闯入！" if len(current_intruder_ids) > 0 else "✅ 区域安全"
        latest_status["last_update"] = time.strftime("%H:%M:%S")

        annotated_frame = fence.draw_fence(annotated_frame, is_alert=(len(current_intruder_ids) > 0))
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')


# 路由部分保持不变...
@app.route('/')
def index(): return render_template('index.html')


@app.route('/video_feed')
def video_feed(): return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/get_status')
def get_status(): return jsonify(latest_status)


@app.route('/get_history')
def get_history():
    history = []
    log_path = os.path.join(root_path, "data", "logs", "intrusion_history.csv")
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            history = list(reader)[-10:][::-1]
    return jsonify(history)


@app.route('/video_storage/<path:filename>')
def serve_video(filename):
    return send_from_directory(os.path.join(root_path, "data", "videos"), filename)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, threaded=True)