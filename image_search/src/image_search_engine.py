import os
import csv
from pathlib import Path
from datetime import datetime

# HuggingFace 国内镜像（在 import transformers 前设置）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLIP_MODEL_DIR = PROJECT_ROOT / "models" / "clip-ViT-B-32"

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    chromadb = None
    Settings = None

try:
    from sentence_transformers import SentenceTransformer
    from PIL import Image
except ImportError:
    SentenceTransformer = None
    Image = None


class ImageSearchEngine:
    """图片搜索引擎：优先使用 CLIP + ChromaDB，失败时降级为 CSV 元数据检索。"""

    def __init__(self, persist_dir="data/vector_db", model_name=None):
        self.model = None
        self.collection = None
        self.vector_available = False
        self.fallback_reason = None
        self.metadata_rows = []
        self.last_image_dir = None
        self.last_csv_path = None

        try:
            if chromadb is None or Settings is None:
                raise RuntimeError("缺少 chromadb 依赖")
            if SentenceTransformer is None or Image is None:
                raise RuntimeError("缺少 sentence-transformers 或 Pillow 依赖")

            resolved_model = model_name or (
                str(DEFAULT_CLIP_MODEL_DIR) if DEFAULT_CLIP_MODEL_DIR.exists() else "clip-ViT-B-32"
            )
            self.model = SentenceTransformer(resolved_model)
            os.makedirs(persist_dir, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(
                path=persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            self.collection = self.chroma_client.get_or_create_collection(
                name="petguard_images",
                metadata={"hnsw:space": "cosine"},
            )
            self.vector_available = True
        except Exception as exc:
            self.fallback_reason = str(exc)

    # ── 编码 ──────────────────────────────────────────

    def encode_image(self, image_path):
        """将单张图片编码为向量"""
        return self.model.encode(Image.open(image_path)).tolist()

    def encode_text(self, text):
        """将文本编码为向量（与图片在同一语义空间）"""
        return self.model.encode(text).tolist()

    def encode_images_batch(self, image_paths, batch_size=32):
        """批量编码图片"""
        images = [Image.open(p) for p in image_paths]
        return self.model.encode(images, batch_size=batch_size).tolist()

    # ── 索引管理 ──────────────────────────────────────

    def index_image(self, image_path, metadata=None):
        """索引单张图片"""
        if not self.vector_available:
            return False

        image_path = Path(image_path)
        if not image_path.exists():
            return False

        image_id = image_path.name
        embedding = self.encode_image(image_path)

        meta = dict(metadata or {})
        meta.setdefault("Image_File", image_id)

        self.collection.upsert(
            ids=[image_id],
            embeddings=[embedding],
            metadatas=[meta],
        )
        return True

    def index_images_from_csv(self, image_dir, csv_path, force=False):
        """从历史记录CSV批量索引所有图片

        Args:
            image_dir: 图片目录
            csv_path: 抓拍历史CSV路径
            force: 是否强制重新索引

        Returns:
            dict: {indexed, skipped, total}
        """
        self.last_image_dir = str(image_dir)
        self.last_csv_path = str(csv_path)
        indexed = 0
        skipped = 0

        if not os.path.exists(csv_path):
            return {"indexed": 0, "skipped": 0, "total": 0, "error": "CSV文件不存在"}

        rows = self._load_metadata_rows(image_dir, csv_path)
        if not self.vector_available:
            return {
                "indexed": 0,
                "skipped": 0,
                "total": len(rows),
                "mode": "metadata",
                "warning": f"CLIP 向量模型不可用，已启用离线元数据检索：{self.fallback_reason}",
            }

        # 获取已索引的图片ID
        existing_ids = set()
        if not force and self.collection.count() > 0:
            existing_ids = set(self.collection.get()["ids"])

        image_dir = Path(image_dir)
        to_index = []

        for row in rows:
            image_file = row.get("Image_File", "")
            if not image_file:
                continue
            if not force and image_file in existing_ids:
                skipped += 1
                continue

            image_path = image_dir / image_file
            if not image_path.exists():
                skipped += 1
                continue

            # 预处理元数据
            meta = {
                "Time": row.get("Time", ""),
                "Pet_ID": row.get("Pet_ID", ""),
                "Image_File": image_file,
                "Status": row.get("Status", ""),
            }
            to_index.append((str(image_path), image_file, meta))

        # 批量索引
        if to_index:
            batch_size = 32
            for i in range(0, len(to_index), batch_size):
                batch = to_index[i : i + batch_size]
                paths = [b[0] for b in batch]
                ids = [b[1] for b in batch]
                metas = [b[2] for b in batch]

                embeddings = self.encode_images_batch(paths)
                self.collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metas,
                )
                indexed += len(batch)

        return {
            "indexed": indexed,
            "skipped": skipped,
            "total": len(rows),
        }

    def index_new_images(self, image_dir, csv_path):
        """仅索引未索引的新图片（增量）"""
        return self.index_images_from_csv(image_dir, csv_path, force=False)

    def remove_image(self, image_id):
        """从索引中移除图片"""
        if not self.vector_available:
            return False

        try:
            self.collection.delete(ids=[image_id])
            return True
        except Exception:
            return False

    def get_index_stats(self):
        """获取索引统计"""
        if not self.vector_available:
            count = len(self.metadata_rows)
            if not count and self.last_image_dir and self.last_csv_path:
                count = len(self._load_metadata_rows(self.last_image_dir, self.last_csv_path))
            return {
                "total_indexed": count,
                "mode": "metadata",
                "vector_available": False,
                "fallback_reason": self.fallback_reason,
            }

        count = self.collection.count()
        return {
            "total_indexed": count,
            "mode": "vector",
            "vector_available": True,
            "fallback_reason": None,
        }

    # ── 搜索 ──────────────────────────────────────────

    def search(self, query, top_k=20):
        """自然语言搜索图片

        Args:
            query: 用户搜索文本
            top_k: 返回结果数

        Returns:
            list[dict]: 搜索结果
        """
        if not self.vector_available:
            return self._search_metadata(query, top_k=top_k)

        query_embedding = self.encode_text(query)
        return self._search_by_vector(query_embedding, top_k=top_k)

    def search_with_filters(self, query, top_k=20, pet_id=None, start_date=None, end_date=None):
        """带过滤条件的搜索"""
        if not self.vector_available:
            return self._search_metadata(
                query,
                top_k=top_k,
                pet_id=pet_id,
                start_date=start_date,
                end_date=end_date,
            )

        query_embedding = self.encode_text(query)

        # 构建过滤条件
        where = {}
        filters = []

        if pet_id:
            filters.append({"Pet_ID": str(pet_id)})

        if start_date or end_date:
            time_filters = []
            if start_date:
                time_filters.append({"Time": {"$gte": start_date}})
            if end_date:
                time_filters.append({"Time": {"$lte": end_date}})
            if len(time_filters) == 1:
                filters.append(time_filters[0])
            elif len(time_filters) == 2:
                filters.append({"$and": time_filters})

        if len(filters) == 1:
            where = filters[0]
        elif len(filters) > 1:
            where = {"$and": filters}

        return self._search_by_vector(query_embedding, top_k=top_k, where=where)

    def _search_by_vector(self, embedding, top_k=20, where=None):
        """向量检索"""
        kwargs = {
            "query_embeddings": [embedding],
            "n_results": min(top_k, self.collection.count() or 1),
        }
        if where:
            kwargs["where"] = where

        if self.collection.count() == 0:
            return []

        result = self.collection.query(**kwargs)

        items = []
        for i in range(len(result["ids"][0])):
            meta = result["metadatas"][0][i]
            items.append({
                "id": result["ids"][0][i],
                "image_file": meta.get("Image_File", result["ids"][0][i]),
                "pet_id": meta.get("Pet_ID", ""),
                "time": meta.get("Time", ""),
                "status": meta.get("Status", ""),
                "score": 1 - result["distances"][0][i] if result["distances"] else 0,
            })

        return items

    def rebuild_index(self, image_dir, csv_path):
        """重建索引"""
        self.delete_all()
        return self.index_images_from_csv(image_dir, csv_path, force=True)

    def delete_all(self):
        """清空索引"""
        if not self.vector_available:
            self.metadata_rows = []
            return

        all_ids = self.collection.get()["ids"]
        if all_ids:
            self.collection.delete(ids=all_ids)

    def _load_metadata_rows(self, image_dir, csv_path):
        """读取 CSV，并过滤掉图片文件不存在的记录。"""
        self.last_image_dir = str(image_dir)
        self.last_csv_path = str(csv_path)

        if not os.path.exists(csv_path):
            self.metadata_rows = []
            return []

        image_dir = Path(image_dir)
        rows = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                image_file = row.get("Image_File", "")
                if not image_file:
                    continue
                if not (image_dir / image_file).exists():
                    continue
                rows.append({
                    "Time": row.get("Time", ""),
                    "Pet_ID": row.get("Pet_ID", ""),
                    "Image_File": image_file,
                    "Status": row.get("Status", ""),
                })

        self.metadata_rows = rows
        return rows

    def _search_metadata(self, query, top_k=20, pet_id=None, start_date=None, end_date=None):
        """离线模式：基于 CSV 元数据做关键词、时间、ID 检索。"""
        rows = list(self.metadata_rows)
        if not rows and self.last_image_dir and self.last_csv_path:
            rows = self._load_metadata_rows(self.last_image_dir, self.last_csv_path)

        query_text = (query or "").lower()
        query_tokens = [token for token in query_text.replace("_", " ").replace("-", " ").split() if token]
        scored = []

        for row in rows:
            row_pet_id = str(row.get("Pet_ID", ""))
            row_time = row.get("Time", "")
            row_file = row.get("Image_File", "")

            if pet_id and row_pet_id != str(pet_id):
                continue
            if start_date and row_time[:10] < str(start_date):
                continue
            if end_date and row_time[:10] > str(end_date):
                continue

            haystack = f"{row_pet_id} {row_time} {row_file} {row.get('Status', '')}".lower()
            score = 0.45

            if query_text and query_text in haystack:
                score += 0.35
            if query_tokens:
                score += min(0.35, sum(0.08 for token in query_tokens if token in haystack))
            if pet_id:
                score += 0.15
            if start_date or end_date:
                score += 0.1

            scored.append({
                "id": row_file,
                "image_file": row_file,
                "pet_id": row_pet_id,
                "time": row_time,
                "status": row.get("Status", ""),
                "score": min(score, 0.98),
                "mode": "metadata",
            })

        scored.sort(key=lambda item: (item["score"], item["time"]), reverse=True)
        return scored[:top_k]
