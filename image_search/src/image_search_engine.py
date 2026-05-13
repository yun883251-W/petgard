import os
import csv
from pathlib import Path
from datetime import datetime

# HuggingFace 国内镜像（在 import transformers 前设置）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from PIL import Image


class ImageSearchEngine:
    """图片搜索引擎：CLIP向量化 + ChromaDB检索"""

    def __init__(self, persist_dir="data/vector_db", model_name="clip-ViT-B-32"):
        self.model = SentenceTransformer(model_name)

        os.makedirs(persist_dir, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="petguard_images",
            metadata={"hnsw:space": "cosine"},
        )

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
        indexed = 0
        skipped = 0

        if not os.path.exists(csv_path):
            return {"indexed": 0, "skipped": 0, "total": 0, "error": "CSV文件不存在"}

        # 获取已索引的图片ID
        existing_ids = set()
        if not force and self.collection.count() > 0:
            existing_ids = set(self.collection.get()["ids"])

        # 读取CSV
        rows = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

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
        try:
            self.collection.delete(ids=[image_id])
            return True
        except Exception:
            return False

    def get_index_stats(self):
        """获取索引统计"""
        count = self.collection.count()
        return {
            "total_indexed": count,
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
        query_embedding = self.encode_text(query)
        return self._search_by_vector(query_embedding, top_k=top_k)

    def search_with_filters(self, query, top_k=20, pet_id=None, start_date=None, end_date=None):
        """带过滤条件的搜索"""
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
        all_ids = self.collection.get()["ids"]
        if all_ids:
            self.collection.delete(ids=all_ids)
