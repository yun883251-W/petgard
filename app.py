import os
import sys
import cv2
import time
import json
import csv
from flask import Flask, render_template, Response, jsonify, send_from_directory, request
from datetime import datetime
import threading

# 路径修复
root_path = os.path.dirname(os.path.abspath(__file__))
if root_path not in sys.path:
    sys.path.append(root_path)

from src.detector import PetDetector
from src.fence import VirtualFence
from src.alerts import AlertManager
from src.config_manager import ConfigManager
from src.stats import StatisticsManager
from src.capture_history_manager import CaptureHistoryManager

app = Flask(__name__)

# 初始化配置管理器
config_manager = ConfigManager()

# --- 配置 ---
VIDEO_SOURCE = os.path.join(root_path, "data", "samples", "test_video.mp4")
CONFIG_FILE = os.path.join(root_path, "config", "roi_config.json")

# 使用配置管理器加载参数
detector = PetDetector(config_manager.get('detection.model_path', 'models/yolov8s.pt'))
alert_mgr = AlertManager()  # 初始化录像管理器

# 加载围栏配置
try:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    fence = VirtualFence(config['polygon'])
except FileNotFoundError:
    # 如果没有配置文件，使用默认值
    fence = VirtualFence([[100, 100], [200, 100], [200, 200], [100, 200]])

# 初始化统计管理器
stats_manager = StatisticsManager()
# 初始化抓拍历史管理器
capture_history_manager = CaptureHistoryManager()

latest_status = {"intruder_count": 0, "status_text": "系统运行中", "last_update": "", "fps": 0}
last_seen_time = {}  # 存放目标最后触发抓拍时间，避免重复抓拍

# 全局变量用于控制监控循环
monitoring_active = True


def generate_frames():
    global latest_status, monitoring_active
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
    frame_count = 0
    start_time = time.time()

    while monitoring_active:
        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        frame_count += 1
        current_time = time.time()
        if current_time - start_time >= 1:  # 每秒更新一次FPS
            latest_status["fps"] = frame_count / (current_time - start_time)
            frame_count = 0
            start_time = current_time

        # 使用配置管理器的参数
        conf_thresh = config_manager.get('detection.confidence_threshold', 0.4)
        results = detector.track(frame, conf=conf_thresh)
        annotated_frame = results.plot()

        current_intruder_ids = set()
        if results.boxes is not None and results.boxes.id is not None:
            boxes = results.boxes.xyxy.cpu().numpy()
            track_ids = results.boxes.id.int().cpu().numpy()

            for box, tid in zip(boxes, track_ids):
                foot_point = (int((box[0] + box[2]) / 2), int(box[3]))

                # --- 核心修复：触发图片抓拍逻辑 ---
                if fence.is_intruding(foot_point):
                    current_intruder_ids.add(tid)

                    # 只抓拍一张图片，不再进行持续录像
                    if tid not in last_seen_time or (time.time() - last_seen_time[tid] > 5):  # 至少间隔5秒才重新抓拍
                        image_path = alert_mgr.capture_intrusion_alert(annotated_frame, tid)
                        last_seen_time[tid] = time.time()
                        print(f"📸 [已抓拍] 目标 ID:{tid} 进入禁区，图片已保存至: {image_path}")

        # 更新 Web 状态
        latest_status["intruder_count"] = len(current_intruder_ids)
        latest_status["status_text"] = "🚨 发现违规闯入！" if len(current_intruder_ids) > 0 else "✅ 区域安全"
        latest_status["last_update"] = time.strftime("%H:%M:%S")

        annotated_frame = fence.draw_fence(annotated_frame, is_alert=(len(current_intruder_ids) > 0))
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    cap.release()


# API路由部分
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/capture_history')
def capture_history():
    """抓拍历史管理系统页面"""
    return render_template('capture_history.html')


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/get_status')
def get_status():
    return jsonify(latest_status)


@app.route('/get_history')
def get_history():
    history = []
    log_path = os.path.join(root_path, "data", "logs", "intrusion_history.csv")
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            history = list(reader)[-10:][::-1]

    # 将历史记录转换为包含图片信息的格式
    processed_history = []
    for record in history:
        processed_record = {
            'Time': record.get('Time', ''),
            'Pet_ID': record.get('Pet_ID', ''),
            'Image_File': record.get('Image_File', ''),  # 图片文件名
            'has_video': bool(record.get('Video_File', ''))  # 是否有视频
        }
        processed_history.append(processed_record)

    return jsonify(processed_history)


@app.route('/get_statistics')
def get_statistics():
    """获取系统统计信息"""
    stats = {
        'daily': stats_manager.get_daily_stats(),
        'top_intruders': stats_manager.get_top_intruders(),
        'hourly': stats_manager.get_hourly_pattern(),
        'total': stats_manager.get_total_stats()
    }
    return jsonify(stats)


@app.route('/image_storage/<path:filename>')
def serve_image(filename):
    """提供图片文件服务"""
    return send_from_directory(os.path.join(root_path, "data", "images"), filename)


@app.route('/api/config')
def get_config():
    """获取当前配置"""
    return jsonify(config_manager.config)


@app.route('/api/delete_capture', methods=['POST'])
def delete_capture():
    """删除特定的抓拍记录"""
    try:
        data = request.get_json()
        image_filename = data.get('image_filename')

        if not image_filename:
            return jsonify({"success": False, "error": "缺少图片文件名"}), 400

        success = capture_history_manager.delete_capture_record(image_filename)

        if success:
            return jsonify({"success": True, "message": "记录删除成功"})
        else:
            return jsonify({"success": False, "error": "删除失败"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/search_captures', methods=['POST'])
def search_captures():
    """搜索抓拍记录"""
    try:
        data = request.get_json()
        search_term = data.get('search_term', '')
        pet_id_filter = data.get('pet_id_filter', '')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')

        # 解析日期字符串
        start_date = None
        end_date = None

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        if end_date_str:
            # 设置结束时间为当天的23:59:59
            end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d')
            end_date = datetime(end_date_obj.year, end_date_obj.month, end_date_obj.day, 23, 59, 59)

        results = capture_history_manager.search_records(
            search_term=search_term,
            pet_id_filter=pet_id_filter,
            start_date=start_date,
            end_date=end_date
        )

        # 限制结果数量以防止页面过载
        limited_results = results[-50:]  # 只返回最近的50条记录

        return jsonify(limited_results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/system_status')
def system_status():
    """获取系统运行状态"""
    return jsonify({
        "status": "running" if monitoring_active else "stopped",
        "uptime": time.time() - start_time if 'start_time' in globals() else 0,
        "video_source": VIDEO_SOURCE,
        "model_path": config_manager.get('detection.model_path'),
        "fence_enabled": config_manager.get('fence.enable_fencing', True)
    })


def start_monitoring():
    """启动监控服务"""
    global monitoring_active
    monitoring_active = True

    # 启动视频捕获线程
    cap_thread = threading.Thread(target=generate_frames)
    cap_thread.daemon = True
    cap_thread.start()


if __name__ == "__main__":
    port = config_manager.get('ui.web_port', 5000)
    host = config_manager.get('ui.web_host', '0.0.0.0')

    # 启动监控服务
    start_monitoring()

    # 启动Flask应用
    app.run(host=host, port=port, threaded=True)