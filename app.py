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

# 共享帧缓冲区：后台监控线程写入，HTTP流读取
latest_annotated_frame = None
frame_buffer_lock = threading.Lock()


def run_monitoring():
    """后台监控线程：独立读取视频帧、执行检测、更新状态和共享帧缓冲区"""
    global latest_status, latest_annotated_frame, monitoring_active
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    frame_count = 0
    ts = time.time()

    while monitoring_active:
        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        frame_count += 1
        now = time.time()
        if now - ts >= 1:
            latest_status["fps"] = frame_count / (now - ts)
            frame_count = 0
            ts = now

        conf_thresh = config_manager.get('detection.confidence_threshold', 0.4)
        results = detector.track(frame, conf=conf_thresh)

        current_intruder_ids = set()
        has_boxes = results.boxes is not None and results.boxes.id is not None

        if has_boxes:
            annotated_frame = results.plot()
            boxes = results.boxes.xyxy.cpu().numpy()
            track_ids = results.boxes.id.int().cpu().numpy()

            for box, tid in zip(boxes, track_ids):
                foot_point = (int((box[0] + box[2]) / 2), int(box[3]))
                if fence.is_intruding(foot_point):
                    current_intruder_ids.add(tid)
                    if tid not in last_seen_time or (time.time() - last_seen_time[tid] > 5):
                        alert_mgr.capture_intrusion_alert(annotated_frame, tid)
                        last_seen_time[tid] = time.time()
        else:
            annotated_frame = frame.copy()

        latest_status["intruder_count"] = len(current_intruder_ids)
        latest_status["status_text"] = "🚨 发现违规闯入！" if len(current_intruder_ids) > 0 else "✅ 区域安全"
        latest_status["last_update"] = time.strftime("%H:%M:%S")

        annotated_frame = fence.draw_fence(annotated_frame, is_alert=(len(current_intruder_ids) > 0))

        with frame_buffer_lock:
            latest_annotated_frame = annotated_frame

    cap.release()


def generate_frames():
    """HTTP 视频流：从共享缓冲区读取最新帧并逐帧输出"""
    global latest_annotated_frame
    while monitoring_active:
        with frame_buffer_lock:
            if latest_annotated_frame is not None:
                ret, buffer = cv2.imencode('.jpg', latest_annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.03)  # 约 30 FPS


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
    """获取抓拍历史记录（支持服务端分页）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    history = []
    log_path = os.path.join(root_path, "data", "logs", "intrusion_history.csv")
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            history = list(reader)

    total = len(history)
    # 倒序（最新的在前）
    history.reverse()

    # 分页
    start = (page - 1) * per_page
    end = start + per_page
    page_data = history[start:end]

    # 统一格式
    processed = []
    for record in page_data:
        processed.append({
            'Time': record.get('Time', ''),
            'Pet_ID': record.get('Pet_ID', ''),
            'Image_File': record.get('Image_File', ''),
        })

    return jsonify({
        'records': processed,
        'total': total,
        'page': page,
        'per_page': per_page
    })


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


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'POST':
        try:
            new_config = request.get_json()
            if new_config:
                config_manager.update(new_config)
                return jsonify({"success": True, "message": "配置已保存"})
            return jsonify({"success": False, "error": "无效的配置数据"}), 400
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
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
    """启动后台监控线程"""
    global monitoring_active
    monitoring_active = True

    monitor_thread = threading.Thread(target=run_monitoring, daemon=True)
    monitor_thread.start()


# 在程序关闭时清理资源
@app.teardown_appcontext
def shutdown_hook(error):
    alert_mgr.shutdown()


if __name__ == "__main__":
    port = config_manager.get('ui.web_port', 5000)
    host = config_manager.get('ui.web_host', '0.0.0.0')

    # 启动监控服务
    start_monitoring()

    # 启动Flask应用
    try:
        app.run(host=host, port=port, threaded=True)
    except KeyboardInterrupt:
        print("\n👋 正在关闭系统...")
        monitoring_active = False
        alert_mgr.shutdown()