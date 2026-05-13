# PetGuard 智能图片搜索

基于 CLIP 向量化 + ChromaDB + DeepSeek LLM 的宠物闯入截图搜索系统。

## 架构

```
用户输入"昨晚那只黑猫"
    │
    ▼
DeepSeek LLM ──→ 分析查询意图，提取搜索关键词、时间范围、宠物ID
    │
    ▼
CLIP 模型 ──→ 将搜索词转为向量（与图片在同一语义空间）
    │
    ▼
ChromaDB ──→ 余弦相似度检索，找出最匹配的图片
    │
    ▼
返回结果 ──→ DeepSeek 组织自然语言回答 + 图片网格展示
```

### 核心组件

| 组件 | 技术 | 职责 |
|------|------|------|
| 图片编码 | CLIP (`clip-ViT-B-32`) | 将图片和文本映射到同一向量空间 |
| 向量存储 | ChromaDB（嵌入式） | 持久化向量索引，支持元数据过滤 |
| 查询理解 | DeepSeek API (`deepseek-chat`) | 从自然语言中提取搜索意图 |
| 回答生成 | DeepSeek API | 根据搜索结果组织对话式回答 |
| Web 服务 | Flask | API + 搜索界面 |

## 文件结构

```
image_search/
├── app.py                          # Flask 入口，API 路由
├── .env                            # 环境变量配置
├── requirements.txt                # Python 依赖
├── src/
│   ├── image_search_engine.py      # 搜索引擎（CLIP + ChromaDB）
│   └── llm_query_processor.py      # LLM 查询处理器（DeepSeek）
├── templates/
│   ├── index.html                  # 首页
│   └── search.html                 # 聊天式搜索界面
└── data/
    └── vector_db/                  # 向量数据库持久化文件
```

## 数据流

1. **索引流程**：读取 PetGuard 的 `intrusion_history.csv` → 获取图片列表 → CLIP 编码 → 存入 ChromaDB
2. **搜索流程**：用户输入 → DeepSeek 分析意图（提取搜索词/时间/宠物ID） → CLIP 将搜索词编码为向量 → ChromaDB 检索 → DeepSeek 组织回答 → 返回结果给前端

## 关键设计

- **纯文本 LLM + CLIP 视觉模型**：不需要多模态 LLM，CLIP 负责"看懂"图片，DeepSeek 负责"理解"查询
- **向量空间统一**：CLIP 将图片和文本编码到同一 512 维向量空间，直接用余弦相似度比较
- **增量索引**：新图片自动跳过，不重复编码
- **元数据过滤**：支持按 Pet_ID、时间范围过滤，与向量检索组合使用

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 首页 |
| GET | `/search` | 搜索界面 |
| POST | `/api/chat` | 聊天搜索（分析+检索+回答） |
| POST | `/api/search` | 纯向量搜索（仅返回结果） |
| POST | `/api/analyze` | 仅分析查询意图（调试用） |
| POST | `/api/index` | 索引所有图片 |
| POST | `/api/index/incremental` | 增量索引新图片 |
| GET | `/api/index/status` | 获取索引状态 |
| POST | `/api/index/rebuild` | 重建索引 |
| POST | `/api/chat/clear` | 清空对话历史 |
| GET | `/images/<filename>` | 获取图片文件 |

## 启动

```bash
cd image_search
pip install -r requirements.txt
python app.py
```

服务默认启动在 `http://localhost:5001`。

搜索界面点击首页的"开始搜索"按钮，或直接访问 `/search`。

## 使用示例

在搜索框输入自然语言描述：

- "今晚的记录" → 搜索今晚的截图
- "ID 3 的宠物" → 查找特定宠物的截图
- "凌晨拍的" → 搜索凌晨时段的截图
- "最近三次闯入" → 查看最近的闯入记录
- "cat"、"dog"、"black cat" → 按图片内容语义搜索

## 依赖

- Python 3.9+
- chromadb >= 1.5.0
- sentence-transformers >= 2.2.0
- openai >= 1.0.0（DeepSeek API 兼容 OpenAI 格式）
- flask >= 2.3.0
- Pillow >= 10.0.0
