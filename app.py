import os
import sys
import cv2
import time
import json
import csv
from flask import Flask, render_template, Response, jsonify, send_from_directory, request
from datetime import datetime, date
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

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

app = Flask(__name__)
start_time = time.time()

if load_dotenv:
    load_dotenv(os.path.join(root_path, ".env"))

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

ai_search_lock = threading.Lock()
ai_search_engine = None
ai_llm_processor = None
ai_search_error = None

IMAGE_SOURCE_DIR = os.getenv("IMAGE_SOURCE_DIR", os.path.join(root_path, "data", "images"))
INTRUSION_CSV = os.getenv("INTRUSION_HISTORY_CSV", os.path.join(root_path, "data", "logs", "intrusion_history.csv"))
VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", os.path.join(root_path, "image_search", "data", "vector_db"))

latest_status = {"intruder_count": 0, "status_text": "系统运行中", "last_update": "", "fps": 0}
last_seen_time = {}  # 存放目标最后触发抓拍时间，避免重复抓拍
intrusion_confirmations = {}  # 连续闯入帧计数，降低单帧误报

# 全局变量用于控制监控循环
monitoring_active = True

# 共享帧缓冲区：后台监控线程写入，HTTP流读取
latest_annotated_frame = None
frame_buffer_lock = threading.Lock()


def get_ai_services():
    """按需加载图片向量检索与大模型查询模块，避免影响实时监控启动。"""
    global ai_search_engine, ai_llm_processor, ai_search_error

    if ai_search_engine and ai_llm_processor:
        return ai_search_engine, ai_llm_processor

    with ai_search_lock:
        if ai_search_engine and ai_llm_processor:
            return ai_search_engine, ai_llm_processor

        try:
            image_search_path = os.path.join(root_path, "image_search")
            if image_search_path not in sys.path:
                sys.path.insert(0, image_search_path)

            from image_search.src.image_search_engine import ImageSearchEngine
            from image_search.src.llm_query_processor import LLMQueryProcessor

            ai_search_engine = ImageSearchEngine(persist_dir=VECTOR_DB_DIR)
            if not ai_search_engine.get_index_stats().get("vector_available", False):
                ai_search_engine.index_new_images(IMAGE_SOURCE_DIR, INTRUSION_CSV)
            ai_llm_processor = LLMQueryProcessor()
            ai_search_error = None
        except Exception as exc:
            ai_search_error = str(exc)
            raise

    return ai_search_engine, ai_llm_processor


def get_ai_index_stats():
    """返回 AI 检索模块状态；依赖不可用时也给前端可展示的状态。"""
    if ai_search_engine:
        return {"available": True, **ai_search_engine.get_index_stats(), "error": None}
    if ai_search_error:
        return {"available": False, "total_indexed": 0, "error": ai_search_error}
    return {"available": None, "total_indexed": 0, "error": "AI 检索模块尚未初始化"}


def build_intelligent_summary():
    """生成首页使用的轻量化智能摘要。"""
    stats = {
        'daily': stats_manager.get_daily_stats(),
        'top_intruders': stats_manager.get_top_intruders(),
        'hourly': stats_manager.get_hourly_pattern(),
        'total': stats_manager.get_total_stats()
    }

    today_key = date.today().isoformat()
    today_count = stats['daily'].get(today_key, 0)
    top_intruder = stats['top_intruders'][0] if stats['top_intruders'] else None
    hourly = stats['hourly'] or {}
    peak_hour = max(hourly, key=hourly.get) if hourly and max(hourly.values()) > 0 else None
    last_event = stats['total'].get('last_event')

    if today_count > 0:
        risk_level = "需要关注"
        suggestion = "今日已有异常抓拍，建议重点查看最近记录并确认围栏区域是否合理。"
    elif top_intruder and top_intruder.get('count', 0) >= 3:
        risk_level = "持续观察"
        suggestion = f"宠物 ID {top_intruder['pet_id']} 出现次数较多，建议作为重点关注对象。"
    else:
        risk_level = "运行平稳"
        suggestion = "当前暂无明显高风险趋势，保持监控和定期索引即可。"

    return {
        "today_count": today_count,
        "total_events": stats['total'].get('total_events', 0),
        "unique_pets": stats['total'].get('unique_pets', 0),
        "last_event": last_event,
        "top_intruder": top_intruder,
        "peak_hour": f"{int(peak_hour):02d}:00" if peak_hour is not None else "暂无",
        "risk_level": risk_level,
        "suggestion": suggestion,
    }


def run_monitoring():
    """后台监控线程：独立读取视频帧、执行检测、更新状态和共享帧缓冲区"""
    global latest_status, latest_annotated_frame, monitoring_active
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    frame_count = 0
    total_frame_count = 0
    processed_frame_count = 0
    ts = time.time()
    last_results = None

    while monitoring_active:
        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        frame_count += 1
        total_frame_count += 1
        now = time.time()
        if now - ts >= 1:
            latest_status["fps"] = frame_count / (now - ts)
            latest_status["inference_fps"] = processed_frame_count / (now - ts)
            frame_count = 0
            processed_frame_count = 0
            ts = now

        conf_thresh = config_manager.get('detection.confidence_threshold', 0.4)
        imgsz = config_manager.get('detection.image_size', 640)
        classes = config_manager.get('detection.classes', [15, 16])
        iou = config_manager.get('detection.iou_threshold', 0.5)
        tracker = config_manager.get('detection.tracker', 'bytetrack.yaml')
        frame_skip = max(1, int(config_manager.get('performance.frame_skip', 1)))
        use_gpu = config_manager.get('performance.use_gpu', True)
        gpu_device = config_manager.get('performance.gpu_device', 0)
        half_precision = config_manager.get('performance.half_precision', False)
        device = gpu_device if use_gpu else 'cpu'

        if total_frame_count % frame_skip == 0 or last_results is None:
            results = detector.track(
                frame,
                conf=conf_thresh,
                imgsz=imgsz,
                classes=classes,
                iou=iou,
                tracker=tracker,
                device=device,
                half=half_precision,
            )
            last_results = results
            processed_frame_count += 1
        else:
            results = last_results

        current_intruder_ids = set()
        raw_intruder_ids = set()
        has_boxes = results.boxes is not None and results.boxes.id is not None

        if has_boxes:
            annotated_frame = results.plot()
            boxes = results.boxes.xyxy.cpu().numpy()
            track_ids = results.boxes.id.int().cpu().numpy()

            for box, tid in zip(boxes, track_ids):
                foot_point = (int((box[0] + box[2]) / 2), int(box[3]))
                if fence.is_intruding(foot_point):
                    raw_intruder_ids.add(int(tid))

            confirm_frames = max(1, int(config_manager.get('detection.intrusion_confirm_frames', 2)))
            capture_interval = float(config_manager.get('detection.capture_interval_seconds', 5))

            for tid in raw_intruder_ids:
                intrusion_confirmations[tid] = intrusion_confirmations.get(tid, 0) + 1
                if intrusion_confirmations[tid] >= confirm_frames:
                    current_intruder_ids.add(tid)
                    if tid not in last_seen_time or (time.time() - last_seen_time[tid] > capture_interval):
                        alert_mgr.capture_intrusion_alert(annotated_frame, tid)
                        last_seen_time[tid] = time.time()

            stale_ids = set(intrusion_confirmations) - raw_intruder_ids
            for tid in stale_ids:
                intrusion_confirmations.pop(tid, None)
        else:
            annotated_frame = frame.copy()
            intrusion_confirmations.clear()

        latest_status["intruder_count"] = len(current_intruder_ids)
        latest_status["raw_intruder_count"] = len(raw_intruder_ids)
        latest_status["status_text"] = "🚨 发现违规闯入！" if len(current_intruder_ids) > 0 else "✅ 区域安全"
        latest_status["last_update"] = time.strftime("%H:%M:%S")
        latest_status["frame_skip"] = frame_skip
        latest_status["confidence_threshold"] = conf_thresh
        latest_status["image_size"] = imgsz

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


@app.route('/ai_analysis')
def ai_analysis():
    """大模型图像数据库分析页面"""
    return render_template('ai_analysis.html')


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


@app.route('/api/intelligent_summary')
def intelligent_summary():
    """获取首页智能摘要。"""
    return jsonify(build_intelligent_summary())


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
        "confidence_threshold": config_manager.get('detection.confidence_threshold'),
        "iou_threshold": config_manager.get('detection.iou_threshold'),
        "image_size": config_manager.get('detection.image_size'),
        "frame_skip": config_manager.get('performance.frame_skip'),
        "intrusion_confirm_frames": config_manager.get('detection.intrusion_confirm_frames'),
        "capture_interval_seconds": config_manager.get('detection.capture_interval_seconds'),
        "fence_enabled": config_manager.get('fence.enable_fencing', True)
    })


@app.route('/api/ai/status')
def ai_status():
    """获取大模型图片数据库模块状态。"""
    return jsonify(get_ai_index_stats())


@app.route('/api/ai/index', methods=['POST'])
def ai_index():
    """为抓拍图片建立或增量更新向量索引。"""
    try:
        data = request.get_json(silent=True) or {}
        force = bool(data.get("force", False))
        search_engine, llm_processor = get_ai_services()

        if force:
            result = search_engine.rebuild_index(IMAGE_SOURCE_DIR, INTRUSION_CSV)
        else:
            result = search_engine.index_new_images(IMAGE_SOURCE_DIR, INTRUSION_CSV)

        return jsonify({
            "success": True,
            **result,
            "summary": llm_processor.summarize_indexing_result(result),
            "stats": search_engine.get_index_stats()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    """自然语言查询抓拍图片数据库，并生成面向用户的中文结论。"""
    try:
        data = request.get_json(force=True)
        query = data.get("query", "").strip()
        if not query:
            return jsonify({"success": False, "error": "查询内容不能为空"}), 400

        search_engine, llm_processor = get_ai_services()
        if search_engine.get_index_stats().get("total_indexed", 0) == 0:
            search_engine.index_new_images(IMAGE_SOURCE_DIR, INTRUSION_CSV)

        analysis = llm_processor.analyze_query(query)
        results = search_engine.search_with_filters(
            query=analysis.get("search_text", query),
            top_k=int(data.get("top_k", 12)),
            pet_id=analysis.get("pet_id"),
            start_date=analysis.get("start_date"),
            end_date=analysis.get("end_date"),
        )
        answer = llm_processor.generate_answer(query, results, analysis)

        return jsonify({
            "success": True,
            "answer": answer,
            "analysis": analysis,
            "results": results,
            "stats": search_engine.get_index_stats()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "status": get_ai_index_stats()}), 500


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
