import json
import os
from openai import OpenAI


# 系统提示词：告知 LLM 它的角色和能力边界
SYSTEM_PROMPT = """你是一个智能图片搜索助手，帮助用户从监控抓拍截图中找到他们想要的图片。

## 你的能力
1. 理解用户的自然语言查询，提取关键信息用于搜索
2. 根据搜索结果，用自然语言回答用户的问题

## 工作流程
- 用户输入查询后，你提取搜索关键词和过滤条件
- 系统会用关键词去向量数据库搜索相似图片
- 你根据搜索结果组织回答

## 搜索关键词提取规则
- 提取图片内容关键词（动物种类、颜色、大小、行为等），**用英文输出**
- 提取时间范围（如果有），格式为 YYYY-MM-DD
- 提取宠物ID（如果有）
- 如果用户提到"最严重""最多"等，标记为按严重程度/数量排序

## 回答风格
- 简洁、友好
- 描述找到了什么、为什么匹配
- 如果搜索结果不理想，诚实告知
- 使用中文回答
"""


class LLMQueryProcessor:
    """LLM查询处理器：理解自然语言搜索意图 + 组织回答"""

    def __init__(self, api_key=None, base_url=None):
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

        if not api_key:
            raise ValueError("需要配置 DEEPSEEK_API_KEY")

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = "deepseek-chat"
        self.conversation_history = []

    def analyze_query(self, user_query):
        """分析用户查询，提取搜索意图

        Returns:
            dict: {
                "search_text": "英文搜索关键词",
                "pet_id": "宠物ID或null",
                "start_date": "起始日期或null",
                "end_date": "结束日期或null",
                "sort_by": "排序方式或null",
                "explanation": "分析说明"
            }
        """
        prompt = f"""分析用户的查询，提取搜索参数。只返回JSON，不要加其他文字。

用户查询：{user_query}

需要提取的字段：
- search_text: 用于向量搜索的英文关键词（描述图片内容，如 "a black dog"、"a cat at night"）
- pet_id: 如果用户指定了宠物ID则填数字，否则null
- start_date: 如果用户指定了起始日期则填YYYY-MM-DD，否则null
- end_date: 如果用户指定了结束日期则填YYYY-MM-DD，否则null
- sort_by: 如果用户提到排序则填"time_desc"或"time_asc"或"relevance"，否则"relevance"
- explanation: 简短说明你理解到的用户意图（中文）

JSON格式返回，不要用markdown代码块。
"""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            result = json.loads(resp.choices[0].message.content)
        except Exception as e:
            # fallback: 直接用用户原文搜索
            result = {
                "search_text": user_query,
                "pet_id": None,
                "start_date": None,
                "end_date": None,
                "sort_by": "relevance",
                "explanation": f"使用原文直接搜索（LLM分析失败: {str(e)}）",
            }

        return result

    def generate_answer(self, user_query, search_results, analysis=None):
        """根据搜索结果生成自然语言回答

        Args:
            user_query: 用户原始查询
            search_results: 搜索结果列表
            analysis: analyze_query 的结果（可选）

        Returns:
            str: 自然语言回答
        """
        # 整理搜索结果文本
        if not search_results:
            context = "没有找到匹配的图片。"
        else:
            lines = []
            for i, r in enumerate(search_results[:10], 1):
                lines.append(
                    f"{i}. 文件：{r['image_file']}，"
                    f"宠物ID：{r['pet_id']}，"
                    f"时间：{r['time']}，"
                    f"相似度：{r['score']:.2f}"
                )
            context = "\n".join(lines)

        prompt = f"""用户提问：{user_query}

搜索结果：
{context}

请根据搜索结果回答用户的问题。要求：
1. 告诉用户找到了几张相关图片
2. 列出匹配的图片和时间
3. 如果结果不理想，诚实告知
4. 引导用户进一步细化搜索（比如问具体时间或宠物）
5. 回答简洁自然

回答：
"""

        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            # 带上最近的对话历史（最多3轮）
            for msg in self.conversation_history[-6:]:
                messages.append(msg)
            messages.append({"role": "user", "content": prompt})

            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            )
            answer = resp.choices[0].message.content

            # 保存对话历史
            self.conversation_history.append({"role": "user", "content": user_query})
            self.conversation_history.append({"role": "assistant", "content": answer})

            # 防止历史过长
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]

            return answer

        except Exception as e:
            return f"抱歉，生成回答时出错：{str(e)}"

    def summarize_indexing_result(self, result):
        """用LLM总结索引结果"""
        prompt = f"""图片索引完成，结果如下：
- 新索引：{result.get('indexed', 0)} 张
- 已跳过（已有）：{result.get('skipped', 0)} 张
- 总计：{result.get('total', 0)} 张

请用一句话总结索引结果。"""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100,
            )
            return resp.choices[0].message.content
        except Exception:
            return f"索引完成：新增 {result.get('indexed', 0)} 张，共 {result.get('total', 0)} 张"

    def clear_history(self):
        """清空对话历史"""
        self.conversation_history.clear()
