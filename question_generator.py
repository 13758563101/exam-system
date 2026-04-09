"""题目生成器 - 知识库提取 + relay 生成"""
import os
import zipfile
import json
import re
import random
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Optional, Any
import relay_client

# 知识库根目录
KB_ROOT = "/vol1/1000/云计算课件/"


def _get_children(topics_container: dict) -> list:
    """从 topics container 中提取子节点列表，处理 attached/topic 两种格式"""
    if isinstance(topics_container, dict):
        # 优先用 attached（JSON格式），fallback 到 topic（XML格式）
        return topics_container.get('attached') or topics_container.get('topic') or []
    return []


def extract_xmind_json(xmind_path: str) -> Optional[Dict]:
    """从 XMind JSON 格式提取内容"""
    try:
        with zipfile.ZipFile(xmind_path) as z:
            with z.open('content.json') as f:
                content = json.load(f)
        if isinstance(content, list) and content:
            return content[0]
        elif isinstance(content, dict):
            return content
    except Exception:
        pass
    return None


def extract_xmind_xml(xmind_path: str) -> Optional[ET.Element]:
    """从 XMind XML 格式提取内容"""
    try:
        with zipfile.ZipFile(xmind_path) as z:
            with z.open('content.xml') as f:
                content = f.read().decode('utf-8')
        ns = {'xmap': 'urn:xmind:xmap:xmlns:content:2.0'}
        root = ET.fromstring(content)
        sheets = root.findall('xmap:sheet', ns)
        if sheets:
            return sheets[0]
    except Exception:
        pass
    return None


def extract_xmind_chapters(xmind_path: str) -> List[Tuple[int, str, str]]:
    """
    提取 XMind 文件中的所有知识点
    返回 [(level, title, note_text), ...]
    level: 缩进层级（0 = 根节点）
    """
    results = []

    # 尝试 JSON 格式
    json_root = extract_xmind_json(xmind_path)

    if json_root:
        def extract_topic(topic: dict, level: int = 0):
            title = topic.get('title', '').strip()
            note_text = ''
            if title:
                notes = topic.get('notes', {})
                if isinstance(notes, dict):
                    plain = notes.get('plain', {})
                    if isinstance(plain, dict):
                        note_text = plain.get('content', '') or ''
                    elif isinstance(plain, str):
                        note_text = plain
                elif isinstance(notes, str):
                    note_text = notes
                results.append((level, title, str(note_text).strip()))

            children = topic.get('children', {})
            for child in _get_children(children):
                extract_topic(child, level + 1)

        root_topic = json_root.get('rootTopic', {})
        extract_topic(root_topic)
    else:
        # 尝试 XML 格式
        ns = {'xmap': 'urn:xmind:xmap:xmlns:content:2.0'}
        sheet = extract_xmind_xml(xmind_path)
        if sheet is None:
            return results

        def extract_xml_topic(node, level: int = 0):
            title_el = node.find('xmap:title', ns)
            title = (title_el.text or '').strip() if title_el is not None else ''
            note_text = ''
            notes_el = node.find('xmap:notes', ns)
            if notes_el is not None:
                plain = notes_el.find('xmap:plain', ns)
                if plain is not None and plain.text:
                    note_text = plain.text.strip()
            if title:
                results.append((level, title, note_text))
            children = node.find('xmap:children', ns)
            if children is not None:
                for topics_el in children.findall('xmap:topics', ns):
                    for child in topics_el.findall('xmap:topic', ns):
                        extract_xml_topic(child, level + 1)

        root_topic = sheet.find('xmap:topic', ns)
        if root_topic is not None:
            extract_xml_topic(root_topic, 0)

    return results


def stage_from_path(xmind_path: str) -> str:
    """根据路径判断属于哪个阶段"""
    path_lower = xmind_path.lower()
    name_lower = os.path.basename(xmind_path).lower()
    if 'linux' in path_lower or '第一阶段' in path_lower or 'linux' in name_lower:
        return 'Linux'
    elif 'mysql' in path_lower or '第二阶段' in path_lower or 'mysql' in name_lower:
        return 'MySQL'
    elif 'shell' in path_lower or '第三阶段' in path_lower or 'bash' in name_lower:
        return 'Shell'
    elif '高并发' in path_lower or '第四阶段' in path_lower or 'high' in name_lower:
        return '高并发'
    elif any(k in path_lower for k in ['docker', 'k8s', 'kubernetes', '第五阶段', 'container']):
        return 'K8S'
    elif 'nginx' in path_lower:
        return '高并发'
    return 'Linux'


def extract_all_knowledge() -> List[Dict[str, Any]]:
    """扫描知识库，提取所有知识点"""
    all_knowledge = []
    if not os.path.exists(KB_ROOT):
        print(f"[知识库] 路径不存在: {KB_ROOT}")
        return all_knowledge

    for root, dirs, files in os.walk(KB_ROOT):
        for fname in files:
            if not fname.lower().endswith('.xmind'):
                continue
            xmind_path = os.path.join(root, fname)
            chapters = extract_xmind_chapters(xmind_path)
            source = stage_from_path(xmind_path)

            # 提取章节名（第一个 level=1 的节点）
            chapter = ''
            for lvl, title, note in chapters:
                if lvl == 1:
                    chapter = title
                    break

            for lvl, title, note in chapters:
                if not title or lvl < 1:
                    continue
                # 跳过太短的内容
                if len(title) < 2:
                    continue
                all_knowledge.append({
                    'source': source,
                    'chapter': chapter or os.path.basename(xmind_path),
                    'topic': title,
                    'content': note or title,
                    'path': xmind_path
                })

    print(f"[知识库] 从 {KB_ROOT} 提取到 {len(all_knowledge)} 个知识点")
    return all_knowledge


def generate_question_from_knowledge(knowledge: Dict[str, Any],
                                     q_type: str = 'choice') -> Optional[Dict[str, Any]]:
    """基于知识点调用 relay 生成题目"""
    topic = knowledge.get('topic', '')
    content = knowledge.get('content', topic)
    result = relay_client.generate_question(content, topic, q_type)
    if not result:
        return None
    result['source'] = knowledge.get('source', 'Linux')
    result['chapter'] = knowledge.get('chapter', '')
    result['topic'] = topic
    return result


def batch_generate(knowledge_list: List[Dict],
                   q_types: List[str] = None,
                   target_count: int = 5) -> List[Dict[str, Any]]:
    """批量生成题目"""
    if q_types is None:
        q_types = ['choice', 'judge', 'fill']
    generated = []
    shuffled = list(knowledge_list)
    random.shuffle(shuffled)

    for i, knowledge in enumerate(shuffled[:target_count * 2]):
        q_type = random.choice(q_types)
        q_data = generate_question_from_knowledge(knowledge, q_type)
        if q_data:
            review = relay_client.review_question(q_data)
            q_data['review'] = review
            generated.append(q_data)
            if len(generated) >= target_count:
                break
    return generated


if __name__ == '__main__':
    knowledge = extract_all_knowledge()
    print(f"提取到 {len(knowledge)} 个知识点")
    for k in knowledge[:5]:
        print(f"  [{k['source']}] {k['chapter']} / {k['topic']}")
