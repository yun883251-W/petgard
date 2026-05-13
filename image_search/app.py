import os
import sys
from pathlib import Path
from datetime import datetime

# 设置 HuggingFace 国内镜像（import transformers 前必须设置）
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_from_directory,
)

# 加载环境变量
load_dotenv()

# 将上级目录加入路径（用于访问 PetGuard 的 data 目录）
ROOT = Path(__file__).resolve().parent

sys.path.insert(0, str(ROOT))

from src.image_search_engine import ImageSearchEngine
from src.llm_query_processor import LLMQueryProcessor

# ── 配置 ─────────────────────────────────────────────
IMAGE_SOURCE_DIR = os.getenv("IMAGE_SOURCE_DIR", str(ROOT.parent / "data" / "images"))
INTRUSION_CSV = os.getenv("INTRUSION_HISTORY_CSV", str(ROOT.parent / "data" / "logs" / "intrusion_history.csv"))
VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", str(ROOT / "data" / "vector_db"))
PORT = int(os.getenv("PORT", "5001"))

# ── 初始化引擎 ───────────────────────────────────────
print("正在加载图片搜索引擎（CLIP + ChromaDB）...")
search_engine = ImageSearchEngine(persist_dir=VECTOR_DB_DIR)

print("正在初始化 LLM 查询处理器（DeepSeek）...")
llm_processor = LLMQueryProcessor()

# ── Flask ────────────────────────────────────────────
app = Flask(__name__)

# ── LLM 分析接口 ─────────────────────────────────────

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """分析用户查询意图（调试用）"""
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "查询不能为空"}), 400

    result = llm_processor.analyze_query(query)
    return jsonify(result)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """聊天式搜索：分析查询 → 搜索 → LLM回答"""
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "查询不能为空"}), 400

    # 1. LLM 分析查询意图
    analysis = llm_processor.analyze_query(query)

    # 2. 向量搜索
    top_k = data.get("top_k", 20)
    results = search_engine.search_with_filters(
        query=analysis.get("search_text", query),
        top_k=top_k,
        pet_id=analysis.get("pet_id"),
        start_date=analysis.get("start_date"),
        end_date=analysis.get("end_date"),
    )

    # 3. LLM 生成回答
    answer = llm_processor.generate_answer(query, results, analysis)

    return jsonify({
        "answer": answer,
        "results": results,
        "analysis": analysis,
    })


# ── 搜索接口 ─────────────────────────────────────────

@app.route("/api/search", methods=["POST"])
def api_search():
    """直接向量搜索（不带LLM回答，仅返回结果）"""
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "查询不能为空"}), 400

    results = search_engine.search(query, top_k=data.get("top_k", 20))
    return jsonify({"results": results})


# ── 索引管理接口 ─────────────────────────────────────

@app.route("/api/index", methods=["POST"])
def api_index():
    """索引所有图片"""
    data = request.get_json(force=True) or {}
    force = data.get("force", False)

    result = search_engine.index_images_from_csv(
        IMAGE_SOURCE_DIR, INTRUSION_CSV, force=force
    )

    summary = llm_processor.summarize_indexing_result(result)

    return jsonify({
        **result,
        "summary": summary,
    })


@app.route("/api/index/incremental", methods=["POST"])
def api_index_incremental():
    """增量索引（仅新图片）"""
    result = search_engine.index_new_images(IMAGE_SOURCE_DIR, INTRUSION_CSV)

    summary = llm_processor.summarize_indexing_result(result)

    return jsonify({
        **result,
        "summary": summary,
    })


@app.route("/api/index/status", methods=["GET"])
def api_index_status():
    """索引状态"""
    stats = search_engine.get_index_stats()
    return jsonify(stats)


@app.route("/api/index/rebuild", methods=["POST"])
def api_rebuild_index():
    """重建索引"""
    result = search_engine.rebuild_index(IMAGE_SOURCE_DIR, INTRUSION_CSV)
    summary = llm_processor.summarize_indexing_result(result)
    return jsonify({**result, "summary": summary})


# ── 对话历史管理 ─────────────────────────────────────

@app.route("/api/chat/clear", methods=["POST"])
def api_clear_history():
    """清空对话历史"""
    llm_processor.clear_history()
    return jsonify({"success": True})


# ── 图片服务 ─────────────────────────────────────────

@app.route("/images/<path:filename>")
def serve_image(filename):
    """提供抓拍图片（代理到 PetGuard 的图片目录）"""
    return send_from_directory(IMAGE_SOURCE_DIR, filename)


# ── 页面路由 ─────────────────────────────────────────

@app.route("/")
def index():
    stats = search_engine.get_index_stats()
    return render_template("index.html", stats=stats)


@app.route("/search")
def search_page():
    stats = search_engine.get_index_stats()
    return render_template("search.html", stats=stats)


# ── 启动 ─────────────────────────────────────────────

if __name__ == "__main__":
    print(f"PetGuard Search 服务启动 → http://localhost:{PORT}")
    print(f"图片源: {IMAGE_SOURCE_DIR}")
    print(f"CSV: {INTRUSION_CSV}")
    print(f"向量库: {VECTOR_DB_DIR}")
    print(f"已索引: {search_engine.get_index_stats()['total_indexed']} 张")
    app.run(host="0.0.0.0", port=PORT, debug=True)
