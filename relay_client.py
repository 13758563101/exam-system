"""雷神 relay 调用封装"""
import requests
import json
import re
from typing import Dict, Any, List, Optional

RELAY_URL = "http://192.168.31.175:7892"
RELAY_CHAT_URL = f"{RELAY_URL}/chat"
RELAY_REVIEW_URL = f"{RELAY_URL}/review"
DEFAULT_TIMEOUT = 130


class RelayClient:
    def __init__(self, url: str = RELAY_URL):
        self.url = url
        self.history: List[Dict] = []

    def _do_request(self, code: str, language: str = "Python",
                    timeout: int = 120) -> Dict[str, Any]:
        payload = {
            "code": code,
            "language": language,
            "timeout": timeout,
            "history": self.history
        }
        resp = requests.post(self.url, json=payload, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        result = resp.json()
        if isinstance(result, dict):
            summary = result.get('summary', '') or result.get('message', '') or str(result)
            self.history.append({
                "role": "assistant",
                "content": summary[:500]
            })
        return result

    def _extract_json(self, text: str) -> Optional[Dict]:
        """从文本中提取 JSON 对象"""
        # 去除 markdown 代码块
        text = re.sub(r'^```(?:json)?', '', text.strip(), flags=re.MULTILINE).strip('`').strip()
        # 找第一个 { 和最后一个 }
        start = text.find('{')
        if start == -1:
            return None
        # 简单计数找配对
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except Exception:
                        pass
                    break
        return None

    def requests_post_relay(self, prompt: str, language: str = "Chinese", timeout: int = 120) -> Dict[str, Any]:
        """
        直接发送 prompt 给 relay /chat 接口，返回原始 JSON。
        自动记录到 history，避免重复提问。
        """
        payload = {
            "message": prompt,
            "language": language,
            "timeout": timeout,
            "history": self.history[:20]  # 限制 history 长度
        }
        resp = requests.post(RELAY_CHAT_URL, json=payload, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        result = resp.json()
        # 记录到 history
        reply = result.get('reply', '') or ''
        self.history.append({"role": "assistant", "content": reply[:500]})
        return result

    def parse_review_result(self, result: Dict[str, Any], q_type: str) -> Optional[Dict[str, Any]]:
        """
        解析 relay /chat 返回结果，提取题目信息。
        支持两种格式：
        1. 单题: {"question": "...", ...}
        2. 多题: [{"question": "...", ...}, ...] → 返回第一个
        """
        reply = result.get('reply', '')
        if not reply:
            return None

        # 去除可能的 markdown 代码块标记
        reply = re.sub(r'^```json\s*', '', reply.strip(), flags=re.MULTILINE)
        reply = re.sub(r'^```\s*', '', reply.strip(), flags=re.MULTILINE).strip('`').strip()

        # 尝试直接解析
        try:
            data = json.loads(reply)
        except Exception:
            data = self._extract_json(reply)

        if not data:
            return None

        # 多题：返回第一个
        if isinstance(data, list):
            if data and isinstance(data[0], dict) and 'question' in data[0]:
                return data[0]
            return None

        # 单题
        if isinstance(data, dict) and 'question' in data:
            return data

        return None

    def parse_multi_questions(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        解析 relay /chat 返回的多题 JSON 数组。
        支持两种 options 格式：
        1. [{"letter":"A","text":"..."}]  # 标准格式
        2. ["选项A", "选项B", ...]         # 简略格式
        """
        reply = result.get('reply', '')
        if not reply:
            return []

        # 去除 markdown 代码块
        reply = re.sub(r'^```json\s*', '', reply.strip(), flags=re.MULTILINE)
        reply = re.sub(r'^```\s*', '', reply.strip(), flags=re.MULTILINE).strip('`').strip()

        # 找 JSON 数组
        start = reply.find('[')
        end = reply.rfind(']') + 1
        if start == -1 or end == 0:
            return []

        try:
            questions = json.loads(reply[start:end])
        except Exception:
            parsed = self._extract_json(reply)
            if isinstance(parsed, list):
                questions = parsed
            else:
                return []

        results = []
        for q in questions:
            if not isinstance(q, dict) or 'question' not in q:
                continue

            # 标准化 options 格式
            options = q.get('options')
            if options:
                # 如果是字符串数组，转成标准格式
                if options and isinstance(options[0], str):
                    std_options = []
                    for i, opt_text in enumerate(options[:4]):
                        std_options.append({"letter": chr(65 + i), "text": str(opt_text)})
                    options = std_options
                # 确保有 letter 字段
                elif options and isinstance(options[0], dict):
                    for opt in options:
                        if 'letter' not in opt:
                            opt['letter'] = opt.get('label', 'A')
                q['options'] = options
            else:
                q['options'] = []

            results.append(q)

        return results

    def chat(self, message: str, history: list = None) -> str:
        """调用 /chat 端点，直接获取回复文本"""
        resp = requests.post(
            self.url.replace('/review', '/chat'),
            json={"message": message, "history": history or []},
            timeout=DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
        result = resp.json()
        return result.get('reply', '')

    def generate_question(self, code_snippet: str, topic: str,
                          q_type: str = "choice") -> Optional[Dict[str, Any]]:
        """调用 relay /chat 生成一道高质量题目"""
        if q_type == 'choice':
            prompt = (
                f'基于以下知识点，生成一道高质量选择题，返回纯JSON格式（无markdown代码块）：\n'
                f'{{"question":"题目文本（不含选项字母）","options":[{{"letter":"A","text":"选项A"}}],'
                f'"answer":"正确答案字母","analysis":"解析"}}'
                f'\n\n知识点：{topic}\n'
                f'内容摘要：{code_snippet[:800]}'
            )
        elif q_type == 'judge':
            prompt = (
                f'基于以下知识点，生成一道判断题，返回纯JSON格式（无markdown代码块）：\n'
                f'{{"question":"题目文本","answer":"正确","analysis":"解析"}}'
                f'\n\n知识点：{topic}\n'
                f'内容摘要：{code_snippet[:800]}'
            )
        elif q_type == 'fill':
            prompt = (
                f'基于以下知识点，生成一道填空题，题目用____表示填空位置，返回纯JSON格式（无markdown代码块）：\n'
                f'{{"question":"题目文本（用____填空）","answer":"填空内容","analysis":"解析"}}'
                f'\n\n知识点：{topic}\n'
                f'内容摘要：{code_snippet[:800]}'
            )
        elif q_type == 'short_answer':
            prompt = (
                f'基于以下知识点，生成一道简答题，返回纯JSON格式（无markdown代码块）：\n'
                f'{{"question":"题目文本","answer":"参考答案","analysis":"解析"}}'
                f'\n\n知识点：{topic}\n'
                f'内容摘要：{code_snippet[:800]}'
            )
        else:
            prompt = (
                f'基于以下知识点，生成一道{q_type}题目，返回纯JSON格式（无markdown代码块）：\n'
                f'{{"question":"...","answer":"...","analysis":"..."}}'
                f'\n\n知识点：{topic}\n'
                f'内容摘要：{code_snippet[:800]}'
            )

        try:
            result = self.requests_post_relay(prompt, language="Chinese", timeout=120)
            parsed = self.parse_review_result(result, q_type)
            return parsed
        except Exception as e:
            print(f"[RelayClient] generate_question 失败: {e}")
            return None

    def review_question(self, question_data: Dict) -> Dict[str, Any]:
        """审查题目是否有语法/逻辑问题"""
        prompt = (
            "审查以下题目是否有问题（逻辑错误、歧义、答案错误等）。\n\n"
            f"题目：{question_data.get('question','')}\n"
            f"类型：{question_data.get('q_type','choice')}\n"
            f"答案：{question_data.get('answer','')}\n"
            f"选项：{json.dumps(question_data.get('options',[]),ensure_ascii=False)}\n\n"
            '返回JSON格式：\n'
            '{"valid":true/false,"issues":["问题1"],"suggestion":"改进建议"}'
        )
        try:
            result = self._do_request(prompt, language="Python", timeout=60)
            text = json.dumps(result, ensure_ascii=False)
            parsed = self._extract_json(text)
            if parsed:
                return parsed
            return {"valid": True, "issues": [], "suggestion": ""}
        except Exception as e:
            print(f"[RelayClient] review_question 失败: {e}")
            return {"valid": True, "issues": [], "suggestion": ""}

    def reset_history(self):
        self.history = []


_client: Optional[RelayClient] = None


def get_client() -> RelayClient:
    global _client
    if _client is None:
        _client = RelayClient()
    return _client


def requests_post_relay(prompt: str, language: str = "Chinese", timeout: int = 120) -> Dict[str, Any]:
    return get_client().requests_post_relay(prompt, language, timeout)


def parse_review_result(result: Dict[str, Any], q_type: str) -> Optional[Dict[str, Any]]:
    return get_client().parse_review_result(result, q_type)


def generate_question(code_snippet: str, topic: str,
                      q_type: str = "choice") -> Optional[Dict[str, Any]]:
    return get_client().generate_question(code_snippet, topic, q_type)


def review_question(question_data: Dict) -> Dict[str, Any]:
    return get_client().review_question(question_data)
