from flask import Flask, render_template, request, jsonify, send_file, g
from markupsafe import Markup
import json
import os
import requests
import tempfile
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import bleach
from functools import lru_cache, wraps
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from ai_service import AIService

from config.logging_config import setup_logging
from utils.exam_parser import ExamParser
from utils.feedback import FeedbackManager
from config.settings_manager import SettingsManager
from utils.knowledge_generator import KnowledgeGenerator

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'txt'}

# 添加缓存相关常量和函数
CACHE_DIR = 'cache/explanations'
SUBJECTS_DIR = 'data/subjects'

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit
app.config['UPLOAD_FOLDER'] = 'uploads'

# 性能监控装饰器
def performance_monitor(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        result = f(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time

        # 记录慢查询（超过1秒）
        if duration > 1.0:
            logger.warning(f"慢查询警告: {f.__name__} 耗时 {duration:.2f}秒")

        # 在响应头中添加执行时间
        if hasattr(result, 'headers'):
            result.headers['X-Response-Time'] = f"{duration:.3f}s"

        return result
    return decorated_function

# 内存缓存类
class MemoryCache:
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
        self._lock = threading.RLock()

    def get(self, key, default=None):
        with self._lock:
            if key in self._cache:
                # 检查是否过期（默认5分钟）
                if time.time() - self._timestamps[key] < 300:
                    return self._cache[key]
                else:
                    # 清除过期缓存
                    del self._cache[key]
                    del self._timestamps[key]
            return default

    def set(self, key, value, ttl=300):
        with self._lock:
            self._cache[key] = value
            self._timestamps[key] = time.time()

    def delete(self, key):
        with self._lock:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()

# 全局内存缓存实例
memory_cache = MemoryCache()

# 线程池用于异步任务
executor = ThreadPoolExecutor(max_workers=4)

# 初始化日志系统
logger = setup_logging(app)
logger.info("正在初始化应用组件...")

# 初始化工具类
try:
    exam_parser = ExamParser()
    feedback_manager = FeedbackManager()
    settings_manager = SettingsManager()
    logger.info("应用组件初始化完成")
except Exception as e:
    logger.error(f"初始化组件失败: {str(e)}")
    raise

# 确保上传目录存在
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    logger.info(f"创建上传目录: {app.config['UPLOAD_FOLDER']}")
    os.makedirs(app.config['UPLOAD_FOLDER'])

# 确保学科目录存在
if not os.path.exists(SUBJECTS_DIR):
    logger.info(f"创建学科目录: {SUBJECTS_DIR}")
    os.makedirs(SUBJECTS_DIR)

# 初始化AI服务
ai_service = AIService()
logger.info("AI服务初始化完成")

def get_ai_response(prompt):
    """获取AI响应"""
    try:
        # 如果AI服务不可用，使用模拟响应
        if not hasattr(ai_service, 'client') or ai_service.model_type == 'ollama':
            # 检查Ollama是否可用
            try:
                import requests
                response = requests.get("http://10.132.60.111:11434/api/tags", timeout=2)
                if response.status_code != 200:
                    raise Exception("Ollama not available")
            except:
                # 使用模拟响应
                return get_mock_ai_response(prompt)

        return ai_service.generate_response(prompt)
    except Exception as e:
        logger.error(f"AI服务调用失败: {str(e)}")
        return get_mock_ai_response(prompt)

def get_mock_ai_response(prompt):
    """模拟AI响应，用于测试"""
    if "批改和点评" in prompt:
        return json.dumps({
            "score": 8,
            "comment": "答案基本正确，理解了相关概念。建议进一步深入学习相关理论。",
            "knowledge_points": {
                "基础概念": 0.8,
                "理论理解": 0.7,
                "实际应用": 0.6
            }
        }, ensure_ascii=False)
    elif "学习建议" in prompt:
        return "建议加强基础概念的学习，多做练习题巩固理解。重点关注理论与实践的结合。"
    else:
        return "这是一个模拟的AI响应，用于测试目的。"

def get_subject_config_path(subject_name):
    """获取学科配置文件的路径"""
    return os.path.join(SUBJECTS_DIR, subject_name)

def get_subject_knowledge_path(subject_name):
    """获取学科知识库文件的路径"""
    try:
        path = os.path.join(get_subject_config_path(subject_name), 'knowledgebase.json')
        if not os.path.exists(path):
            logger.warning(f"知识库文件不存在: {path}")
            # 创建默认知识库文件
            default_kb = {
                "科目": subject_name,
                "章节": {
                    "第一章 示例章节": {
                        "mainConcepts": ["示例概念1", "示例概念2"],
                        "mainContents": ["示例内容1", "示例内容2"]
                    }
                }
            }
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(default_kb, f, ensure_ascii=False, indent=2)
            logger.info(f"已创建默认知识库文件: {path}")
        return path
    except Exception as e:
        logger.error(f"获取学科 {subject_name} 的知识库路径失败: {str(e)}")
        return None

def get_subject_testmodel_path(subject_name):
    """获取学科考试模板文件的路径"""
    try:
        path = os.path.join(get_subject_config_path(subject_name), 'testmodel.json')
        if not os.path.exists(path):
            logger.warning(f"考试模板文件不存在: {path}")
            # 创建默认考试模板文件
            default_tm = {
                "考试信息": {
                    "考试名称": f"{subject_name}考试",
                    "总时长": "120分钟",
                    "题型列表": [
                        {
                            "题型名称": "单项选择题",
                            "题量": 10,
                            "总分": 20,
                            "考查重点": "对基本概念和理论的掌握",
                            "内容范围": "各章节的基本概念"
                        }
                    ]
                }
            }
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(default_tm, f, ensure_ascii=False, indent=2)
            logger.info(f"已创建默认考试模板文件: {path}")
        return path
    except Exception as e:
        logger.error(f"获取学科 {subject_name} 的考试模板路径失败: {str(e)}")
        return None

def get_available_subjects():
    """获取所有可用的学科"""
    subjects = []
    try:
        if not os.path.exists(SUBJECTS_DIR):
            logger.warning(f"学科目录不存在: {SUBJECTS_DIR}")
            return subjects
            
        for subject in os.listdir(SUBJECTS_DIR):
            try:
                subject_path = os.path.join(SUBJECTS_DIR, subject)
                if not os.path.isdir(subject_path):
                    continue
                    
                kb_path = get_subject_knowledge_path(subject)
                tm_path = get_subject_testmodel_path(subject)
                
                if os.path.exists(kb_path) and os.path.exists(tm_path):
                    subjects.append(subject)
                    logger.debug(f"找到有效学科: {subject}")
                else:
                    logger.warning(f"学科 {subject} 缺少必要的配置文件")
                    
            except Exception as e:
                logger.error(f"处理学科 {subject} 时出错: {str(e)}")
                continue
                
        logger.info(f"成功获取可用学科列表: {subjects}")
        return subjects
        
    except Exception as e:
        logger.error(f"获取可用学科列表失败: {str(e)}")
        return subjects

# 加载知识库数据
@lru_cache(maxsize=32)
def load_raw_knowledge_base(subject_name):
    """加载原始知识库配置（不过滤）"""
    kb_path = get_subject_knowledge_path(subject_name)
    try:
        with open(kb_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 验证数据结构
            if not isinstance(data, dict) or '章节' not in data:
                raise ValueError("知识库文件格式错误")
            logger.info(f"成功加载学科 {subject_name} 的原始知识库")
            return data
    except json.JSONDecodeError as e:
        logger.error(f"知识库文件 {kb_path} JSON解析错误: {str(e)}")
        return create_default_knowledge_base(subject_name)
    except Exception as e:
        logger.error(f"加载学科 {subject_name} 的原始知识库失败: {str(e)}")
        return create_default_knowledge_base(subject_name)

def create_default_knowledge_base(subject_name):
    """创建默认知识库结构"""
    return {
        "科目": subject_name,
        "章节": {
            "第一章 示例章节": {
                "mainConcepts": ["示例概念1", "示例概念2"],
                "mainContents": ["示例内容1", "示例内容2"]
            }
        }
    }

@lru_cache(maxsize=32)
def load_knowledge_base(subject_name):
    """加载知识库配置（根据设置过滤）"""
    try:
        # 获取学科设置
        settings = settings_manager.get_subject_settings(subject_name)
        if not settings:
            logger.warning(f"未找到学科 {subject_name} 的设置，使用默认设置")
            settings = {"enabled_chapters": []}
        
        # 加载原始知识库
        raw_kb = load_raw_knowledge_base(subject_name)
        if not raw_kb:
            logger.error(f"无法加载学科 {subject_name} 的知识库")
            return None
            
        # 过滤章节
        filtered_kb = {
            "科目": raw_kb["科目"],
            "章节": {}
        }
        
        # 如果没有启用任何章节，启用所有章节
        if not settings.get("enabled_chapters"):
            filtered_kb["章节"] = raw_kb["章节"]
        else:
            for chapter in settings["enabled_chapters"]:
                if chapter in raw_kb["章节"]:
                    filtered_kb["章节"][chapter] = raw_kb["章节"][chapter]
                else:
                    logger.warning(f"章节 {chapter} 在知识库中不存在")
        
        logger.info(f"成功加载并过滤学科 {subject_name} 的知识库")
        return filtered_kb
        
    except Exception as e:
        logger.error(f"加载学科 {subject_name} 的知识库失败: {str(e)}")
        return None

# 加载试题模型数据
@lru_cache(maxsize=32)
def load_test_model(subject_name):
    """加载试题模型配置"""
    try:
        tm_path = get_subject_testmodel_path(subject_name)
        with open(tm_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载学科 {subject_name} 的试题模型失败: {str(e)}")
        return {
            "考试信息": {
                "考试名称": f"{subject_name}考试",
                "总时长": "120分钟",
                "题型列表": [
                    {
                        "题型名称": "单项选择题",
                        "题量": 10,
                        "总分": 20,
                        "考查重点": "对基本概念和理论的掌握",
                        "内容范围": "各章节的基本概念"
                    }
                ]
            }
        }

def clear_config_cache(subject_name=None):
    """清除配置缓存"""
    if subject_name:
        load_raw_knowledge_base.cache_clear()
        load_knowledge_base.cache_clear()
        load_test_model.cache_clear()
    else:
        # 清除所有学科的缓存
        for subject in get_available_subjects():
            load_raw_knowledge_base.cache_clear()
            load_knowledge_base.cache_clear()
            load_test_model.cache_clear()

def check_config_updates():
    """检查配置文件是否更新"""
    now = datetime.now()
    
    # 每5分钟检查一次配置更新
    if not hasattr(check_config_updates, 'last_check') or \
       (now - check_config_updates.last_check).total_seconds() > 300:
        check_config_updates.last_check = now
        
        try:
            for subject in get_available_subjects():
                kb_path = get_subject_knowledge_path(subject)
                tm_path = get_subject_testmodel_path(subject)
                
                if not hasattr(check_config_updates, 'last_mtimes'):
                    check_config_updates.last_mtimes = {}
                
                if os.path.exists(kb_path) and os.path.exists(tm_path):
                    kb_mtime = os.path.getmtime(kb_path)
                    tm_mtime = os.path.getmtime(tm_path)
                    
                    if subject not in check_config_updates.last_mtimes or \
                       kb_mtime > check_config_updates.last_mtimes[subject]['kb'] or \
                       tm_mtime > check_config_updates.last_mtimes[subject]['tm']:
                        clear_config_cache(subject)
                        check_config_updates.last_mtimes[subject] = {
                            'kb': kb_mtime,
                            'tm': tm_mtime
                        }
        except Exception as e:
            logger.error(f"检查配置更新时出错: {str(e)}")

@app.before_request
def before_request():
    """请求预处理，检查配置更新"""
    check_config_updates()

# 获取缓存文件路径
def get_cache_path(chapter, concept, concept_type):
    """获取缓存文件路径"""
    # 确保缓存目录存在
    os.makedirs(CACHE_DIR, exist_ok=True)
    # 使用章节名和概念名生成缓存文件名
    safe_name = f"{chapter}_{concept}_{concept_type}".replace('/', '_').replace('\\', '_')
    return os.path.join(CACHE_DIR, f"{safe_name}.json")

# 从缓存加载内容
def load_from_cache(chapter, concept, concept_type):
    """从缓存加载内容"""
    cache_path = get_cache_path(chapter, concept, concept_type)
    try:
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                return cache_data.get('explanation')
        return None
    except Exception as e:
        logger.error(f"读取缓存失败: {str(e)}")
        return None

# 保存内容到缓存
def save_to_cache(chapter, concept, concept_type, explanation):
    """保存内容到缓存"""
    cache_path = get_cache_path(chapter, concept, concept_type)
    try:
        cache_data = {
            'chapter': chapter,
            'concept': concept,
            'type': concept_type,
            'explanation': explanation,
            'timestamp': datetime.now().isoformat()
        }
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存缓存失败: {str(e)}")
        return False

# AI 生成讲解
def generate_explanation(chapter, concept, concept_type='concept'):
    """生成AI讲解"""
    # 根据不同类型生成不同的提示
    if concept_type == 'concept':
        prompt = f"""
        请作为一名数据库教师，详细讲解数据库课程中"{chapter}"章节的概念"{concept}"。
        请使用HTML格式组织内容，可以使用以下标签：h1-h6, p, ul, li, strong, em, code。

        请按照以下结构组织讲解：
        <h2>概念定义</h2>
        <p>用通俗易懂的语言解释这个概念</p>

        <h2>重要特点</h2>
        <ul>
        <li>特点1</li>
        <li>特点2</li>
        </ul>

        <h2>实际应用</h2>
        <p>举例说明该概念在实践中的应用</p>

        <h2>相关概念</h2>
        <ul>
        <li>相关概念1及关系</li>
        <li>相关概念2及关系</li>
        </ul>

        <h2>重点难点</h2>
        <ul>
        <li>重点1</li>
        <li>难点1</li>
        </ul>

        要求：
        - 讲解要通俗易懂，避免过于晦涩的术语
        - 多用具体的例子来说明
        - 突出重点和难点
        - 注意知识点之间的联系
        """
    else:
        prompt = f"""
        请作为一名数据库教师，详细讲解数据库课程中"{chapter}"章节的内容"{concept}"。
        请使用HTML格式组织内容，可以使用以下标签：h1-h6, p, ul, li, strong, em, code。

        请按照以下结构组织讲解：
        <h2>主要内容</h2>
        <p>概述这部分内容的核心要点</p>

        <h2>详细解析</h2>
        <ul>
        <li>要点1详细解释</li>
        <li>要点2详细解释</li>
        </ul>

        <h2>实例讲解</h2>
        <p>结合具体例子进行说明</p>

        <h2>应用场景</h2>
        <ul>
        <li>应用场景1</li>
        <li>应用场景2</li>
        </ul>

        <h2>学习建议</h2>
        <ul>
        <li>建议1</li>
        <li>建议2</li>
        </ul>

        要求：
        - 循序渐进，由浅入深
        - 结合实际案例
        - 突出实践应用
        - 给出具体的学习方法
        """
    
    try:
        response = get_ai_response(prompt)
        return response
    except Exception as e:
        logger.error(f"生成讲解失败: {str(e)}")
        return f"生成讲解时出错: {str(e)}"

# AI 回答问题
def answer_question(chapter, concept, question):
    prompt = f"""
    作为数据库课程教师，请回答学生关于"{chapter}"章节中"{concept}"知识点的以下问题：
    
    问题：{question}
    
    请给出详细的解答，并尽可能举例说明。
    """
    
    try:
        response = get_ai_response(prompt)
        return response
    except Exception as e:
        logger.error(f"回答问题失败: {str(e)}")
        return f"回答问题时出错: {str(e)}"

# 生成试题
def generate_exam_questions(chapters, question_type, count):
    chapter_str = "、".join(chapters)
    logger.info(f"开始生成试题 - 题型: {question_type}, 数量: {count}, 章节: {chapter_str}")

    prompt = f"""
    请根据以下章节内容生成{count}道{question_type}：
    章节：{chapter_str}

    要求：
    1. 题目难度要适中
    2. 涵盖所选章节的重要知识点
    3. 如果是选择题，需要包含4个选项
    4. 确保题目清晰明确
    5. 返回的格式为JSON数组，每个题目包含：
       - content: 题目内容
       - options: 选项（选择题才有）
       - answer: 答案
       - analysis: 解析

    请确保题目内容准确、专业，并符合学科特点。
    """

    try:
        logger.info(f"正在调用AI生成 {question_type} 题目...")
        response = get_ai_response(prompt)

        if not response or response.strip() == "":
            logger.error("AI响应为空")
            return []

        logger.debug(f"AI响应内容: {response[:200]}...")

        # 尝试解析JSON
        try:
            questions = json.loads(response)
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取JSON部分
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                questions = json.loads(json_match.group())
            else:
                logger.error(f"无法从AI响应中提取有效JSON: {response}")
                return []

        # 验证生成的题目格式
        if not isinstance(questions, list):
            logger.error(f"生成的题目不是数组格式，实际类型: {type(questions)}")
            return []

        if len(questions) == 0:
            logger.error("生成的题目数组为空")
            return []

        valid_questions = []
        for i, question in enumerate(questions):
            if not isinstance(question, dict):
                logger.warning(f"第{i+1}题格式不正确，跳过")
                continue

            required_fields = ['content', 'answer', 'analysis']
            missing_fields = [field for field in required_fields if field not in question]
            if missing_fields:
                logger.warning(f"第{i+1}题缺少必要字段: {missing_fields}，跳过")
                continue

            if question_type == '单项选择题' and 'options' not in question:
                logger.warning(f"第{i+1}题是选择题但缺少选项，跳过")
                continue

            valid_questions.append(question)

        logger.info(f"成功生成 {len(valid_questions)} 道有效的 {question_type} 题目")
        return valid_questions[:count]  # 确保不超过要求的数量

    except json.JSONDecodeError as e:
        logger.error(f"试题JSON解析失败: {str(e)}")
        logger.error(f"原始响应: {response}")
        return []
    except Exception as e:
        logger.error(f"生成试题时发生错误: {str(e)}")
        return []

# AI 批改试卷
def review_exam_answer(question, student_answer, knowledge_base):
    prompt = f"""
    请作为数据库教师，对以下试题答案进行批改和点评：

    题目：{question['content']}
    标准答案：{question['answer']}
    学生答案：{student_answer}

    请提供：
    1. 得分（总分 {question['score']} 分）
    2. 详细点评
    3. 涉及的知识点及掌握程度（0-1之间的小数）

    返回格式为JSON，包含：
    {{
        "score": 得分,
        "comment": "点评内容",
        "knowledge_points": {{
            "知识点1": 掌握度,
            "知识点2": 掌握度
        }}
    }}
    """
    
    try:
        response = get_ai_response(prompt)
        return json.loads(response)
    except Exception as e:
        logger.error(f"批改答案失败: {str(e)}")
        return {
            "score": 0,
            "comment": f"批改出错: {str(e)}",
            "knowledge_points": {}
        }

# 生成学习建议
def generate_learning_suggestions(knowledge_analysis):
    weak_points = [point for point, score in knowledge_analysis.items() if score < 0.6]
    medium_points = [point for point, score in knowledge_analysis.items() if 0.6 <= score < 0.8]
    
    prompt = f"""
    请根据以下知识点掌握情况，给出具体的学习建议：
    
    需要重点加强的知识点：{', '.join(weak_points)}
    需要进一步巩固的知识点：{', '.join(medium_points)}
    
    请给出：
    1. 总体学习建议
    2. 针对薄弱知识点的具体学习方法
    3. 推荐的练习方向
    """
    
    try:
        response = get_ai_response(prompt)
        return response
    except Exception as e:
        logger.error(f"生成学习建议失败: {str(e)}")
        return f"生成学习建议时出错: {str(e)}"

def sanitize_ai_response(content):
    """清理和消毒 AI 响应内容"""
    # 允许的 HTML 标签和属性
    allowed_tags = ['p', 'br', 'b', 'i', 'strong', 'em', 'ul', 'ol', 'li', 'code', 'pre']
    allowed_attrs = {'*': ['class']}
    
    # 使用 bleach 清理内容
    cleaned = bleach.clean(
        content,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True
    )
    return Markup(cleaned)

def generate_chapter_content(chapter, chapter_data):
    """生成章节内容的通用函数"""
    results = {
        'mainConcepts': [],
        'mainContents': []
    }

    # 生成主要概念的解释
    for concept in chapter_data.get('mainConcepts', []):
        explanation = generate_explanation(chapter, concept, 'concept')
        safe_explanation = sanitize_ai_response(explanation)
        save_to_cache(chapter, concept, 'concept', safe_explanation)
        results['mainConcepts'].append({
            'concept': concept,
            'explanation': safe_explanation
        })

    # 生成主要内容的解释
    for content in chapter_data.get('mainContents', []):
        explanation = generate_explanation(chapter, content, 'content')
        safe_explanation = sanitize_ai_response(explanation)
        save_to_cache(chapter, content, 'content', safe_explanation)
        results['mainContents'].append({
            'concept': content,
            'explanation': safe_explanation
        })

    return results

@app.route('/')
def index():
    """首页路由"""
    subject = request.args.get('subject', '')
    subjects = get_available_subjects()
    return render_template('index.html', 
                         subject=subject,
                         subjects=subjects)

@app.route('/study')
def study():
    """学习页面路由"""
    subject = request.args.get('subject', '')
    if not subject or subject not in get_available_subjects():
        return render_template('error.html', message='请选择有效的学科')
    
    knowledge_base = load_knowledge_base(subject)
    if not knowledge_base:
        return render_template('error.html', message='无法加载学科知识库，请检查配置文件')
    
    return render_template('study.html', 
                         subject=subject,
                         subjects=get_available_subjects(),
                         knowledge_base=knowledge_base)

@app.route('/exam')
def exam():
    """考试页面路由"""
    subject = request.args.get('subject', '')
    if not subject or subject not in get_available_subjects():
        return render_template('error.html', message='请选择有效的学科')
    
    knowledge_base = load_knowledge_base(subject)
    test_model = load_test_model(subject)
    return render_template('exam.html',
                         subject=subject,
                         subjects=get_available_subjects(),
                         knowledge_base=knowledge_base,
                         test_model=test_model)

@app.route('/exam_taking/<session_id>')
def exam_taking(session_id):
    """考试答题页面路由"""
    session_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}.json")
    if not os.path.exists(session_file):
        return render_template('error.html', message='考试会话不存在或已过期')

    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            exam_session = json.load(f)
        
        # 将考试数据传递给模板
        return render_template('exam_taking.html', exam_data=exam_session.get('exam_data'), session_id=session_id)
    except Exception as e:
        logger.error(f"加载考试会话失败 (ID: {session_id}): {str(e)}")
        return render_template('error.html', message='加载考试数据时出错')

@app.route('/exam_records')
def exam_records():
    """考试记录页面路由"""
    return render_template('exam_records.html')

@app.route('/review')
def review():
    """试卷审批页面路由"""
    subject = request.args.get('subject', '')
    if not subject or subject not in get_available_subjects():
        return render_template('error.html', message='请选择有效的学科')

    return render_template('review.html',
                         subject=subject,
                         subjects=get_available_subjects())

@app.route('/api/explain', methods=['POST'])
@performance_monitor
def get_ai_explanation():
    try:
        data = request.get_json()
        chapter = data.get('chapter')
        concept = data.get('concept')
        concept_type = data.get('type', 'concept')
        force_regenerate = data.get('force_regenerate', False)

        if not all([chapter, concept]):
            return jsonify({'error': '缺少必要参数'}), 400

        # 检查内存缓存
        cache_key = f"explanation_{chapter}_{concept}_{concept_type}"
        if not force_regenerate:
            cached_explanation = memory_cache.get(cache_key)
            if cached_explanation:
                return jsonify({
                    'explanation': cached_explanation,
                    'from_cache': True,
                    'source': 'memory'
                })

            # 尝试从文件缓存加载
            file_cached_explanation = load_from_cache(chapter, concept, concept_type)
            if file_cached_explanation:
                # 同时存入内存缓存
                memory_cache.set(cache_key, file_cached_explanation, ttl=1800)
                return jsonify({
                    'explanation': file_cached_explanation,
                    'from_cache': True,
                    'source': 'file'
                })

        # 生成新的解释
        explanation = generate_explanation(chapter, concept, concept_type)

        # 清理和消毒响应内容
        safe_explanation = sanitize_ai_response(explanation)

        # 保存到文件缓存和内存缓存
        save_to_cache(chapter, concept, concept_type, safe_explanation)
        memory_cache.set(cache_key, safe_explanation, ttl=1800)

        return jsonify({
            'explanation': safe_explanation,
            'from_cache': False,
            'source': 'generated'
        })
    except Exception as e:
        logger.error(f"获取AI解释失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ask', methods=['POST'])
def ask():
    data = request.get_json()
    chapter = data.get('chapter')
    concept = data.get('concept')
    question = data.get('question')
    
    if not all([chapter, concept, question]):
        return jsonify({'error': '缺少必要参数'}), 400
        
    answer = answer_question(chapter, concept, question)
    return jsonify({'answer': answer})

@app.route('/api/generate_exam', methods=['POST'])
def generate_exam():
    try:
        data = request.get_json()
        if not data:
            logger.error("生成试卷请求缺少JSON数据")
            return jsonify({'error': '请求数据格式错误'}), 400

        subject = data.get('subject', '')
        chapters = data.get('chapters', [])
        selected_types = data.get('types', [])

        # 获取题目数量参数
        choice_count = data.get('choice_count', 0)
        judge_count = data.get('judge_count', 0)
        difficulty = data.get('difficulty', 'medium')

        logger.info(f"生成试卷请求 - 学科: {subject}, 章节: {chapters}, 题型: {selected_types}")
        logger.info(f"题目数量 - 选择题: {choice_count}, 判断题: {judge_count}, 难度: {difficulty}")

        if not subject or subject not in get_available_subjects():
            logger.error(f"无效的学科: {subject}, 可用学科: {get_available_subjects()}")
            return jsonify({'error': '请选择有效的学科'}), 400

        if not chapters:
            logger.error("未选择任何章节")
            return jsonify({'error': '请至少选择一个章节'}), 400

        if not selected_types:
            logger.error("未选择任何题型")
            return jsonify({'error': '请至少选择一种题型'}), 400

        # 生成试卷内容
        questions = []
        total_score = 0

        # 生成选择题
        if '单项选择题' in selected_types and choice_count > 0:
            logger.info(f"正在生成 {choice_count} 道选择题...")
            choice_questions = generate_exam_questions(chapters, '单项选择题', choice_count)

            if choice_questions:
                for i, q in enumerate(choice_questions):
                    options = q.get('options', [])
                    answer_text = q.get('answer', '')

                    # 将答案文本转换为选项索引
                    answer_index = 0  # 默认为第一个选项
                    if answer_text and options:
                        # 尝试在选项中找到匹配的答案
                        for idx, option in enumerate(options):
                            if answer_text.strip() == option.strip():
                                answer_index = idx
                                break
                        # 如果没有找到完全匹配，尝试部分匹配
                        if answer_index == 0 and answer_text:
                            for idx, option in enumerate(options):
                                if answer_text.strip() in option.strip() or option.strip() in answer_text.strip():
                                    answer_index = idx
                                    break

                    questions.append({
                        'type': 'choice',
                        'question': q.get('content', ''),
                        'options': options,
                        'answer': answer_index,  # 存储为索引
                        'answer_text': answer_text,  # 保留原始答案文本用于显示
                        'analysis': q.get('analysis', ''),
                        'score': 2  # 每题2分
                    })
                total_score += len(choice_questions) * 2
                logger.info(f"成功生成 {len(choice_questions)} 道选择题")

        # 生成判断题
        if '判断题' in selected_types and judge_count > 0:
            logger.info(f"正在生成 {judge_count} 道判断题...")
            judge_questions = generate_exam_questions(chapters, '判断题', judge_count)

            if judge_questions:
                for i, q in enumerate(judge_questions):
                    answer_text = q.get('answer', '')

                    # 将答案文本转换为布尔值
                    answer_bool = True  # 默认为True
                    if answer_text:
                        answer_lower = answer_text.lower().strip()
                        if any(word in answer_lower for word in ['错', '错误', 'false', '否', '不正确', '不对']):
                            answer_bool = False
                        elif any(word in answer_lower for word in ['对', '正确', 'true', '是', '对的']):
                            answer_bool = True

                    questions.append({
                        'type': 'judge',
                        'question': q.get('content', ''),
                        'answer': answer_bool,  # 存储为布尔值
                        'answer_text': answer_text,  # 保留原始答案文本用于显示
                        'analysis': q.get('analysis', ''),
                        'score': 1  # 每题1分
                    })
                total_score += len(judge_questions) * 1
                logger.info(f"成功生成 {len(judge_questions)} 道判断题")

        if not questions:
            logger.error("未能生成任何题目")
            return jsonify({'error': '未能生成任何题目，请检查章节选择或稍后重试'}), 400

        exam_data = {
            'title': f'{subject}智能试卷',
            'subject': subject,
            'chapters': chapters,
            'difficulty': difficulty,
            'duration': '120分钟',
            'totalScore': total_score,
            'questions': questions,
            'questionCount': len(questions)
        }

        logger.info(f"试卷生成成功 - 总分: {exam_data['totalScore']}, 题目数: {len(questions)}")
        return jsonify(exam_data)

    except Exception as e:
        logger.error(f"生成试卷时发生异常: {str(e)}")
        return jsonify({'error': f'生成试卷时发生错误: {str(e)}'}), 500

@app.route('/api/create_exam_session', methods=['POST'])
def create_exam_session():
    """创建并保存考试会话"""
    try:
        data = request.get_json()
        if not data or 'exam' not in data:
            return jsonify({'error': '无效的试卷数据'}), 400

        exam_data = data['exam']
        
        # 使用更健壮的会话ID生成方式
        session_id = f"exam_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(8).hex()}"
        
        session_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}.json")

        exam_session = {
            'session_id': session_id,
            'exam_data': exam_data,
            'start_time': datetime.now().isoformat(),
            'status': 'not_started',
            'answers': {}
        }

        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(exam_session, f, ensure_ascii=False, indent=2)

        logger.info(f"新的考试会话已创建: {session_id}")
        return jsonify({'session_id': session_id})

    except Exception as e:
        logger.error(f"创建考试会话失败: {str(e)}")
        return jsonify({'error': '创建考试会话时发生服务器错误'}), 500


@app.route('/api/get_saved_answers/<session_id>', methods=['GET'])
def get_saved_answers(session_id):
    """获取已保存的答案"""
    session_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}.json")
    if not os.path.exists(session_file):
        return jsonify({'error': '会话不存在'}), 404
    
    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            exam_session = json.load(f)
        return jsonify({'answers': exam_session.get('answers', {})})
    except Exception as e:
        logger.error(f"获取已存答案失败 (ID: {session_id}): {str(e)}")
        return jsonify({'error': '读取答案失败'}), 500


@app.route('/api/start_exam', methods=['POST'])
def start_exam():
    """开始考试API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '请求数据格式错误'}), 400

        exam_data = data.get('exam')
        student_name = data.get('student_name', '匿名用户')

        if not exam_data:
            return jsonify({'error': '缺少试卷数据'}), 400

        # 生成考试会话ID
        exam_session_id = f"exam_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(str(exam_data))}"

        # 创建考试会话记录
        exam_session = {
            'session_id': exam_session_id,
            'student_name': student_name,
            'exam_data': exam_data,
            'start_time': datetime.now().isoformat(),
            'status': 'in_progress',
            'answers': {},
            'auto_save_count': 0
        }

        # 保存考试会话到临时存储
        session_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{exam_session_id}.json")
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(exam_session, f, ensure_ascii=False, indent=2)

        logger.info(f"考试会话已创建: {exam_session_id}")

        return jsonify({
            'session_id': exam_session_id,
            'exam_data': exam_data,
            'start_time': exam_session['start_time']
        })

    except Exception as e:
        logger.error(f"开始考试失败: {str(e)}")
        return jsonify({'error': f'开始考试失败: {str(e)}'}), 500

@app.route('/api/save_answer', methods=['POST'])
def save_answer():
    """保存答案API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '请求数据格式错误'}), 400

        session_id = data.get('session_id')
        question_index = data.get('question_index')
        answer = data.get('answer')

        if not all([session_id, question_index is not None, answer is not None]):
            return jsonify({'error': '缺少必要参数'}), 400

        # 加载考试会话
        session_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}.json")
        if not os.path.exists(session_file):
            return jsonify({'error': '考试会话不存在'}), 404

        with open(session_file, 'r', encoding='utf-8') as f:
            exam_session = json.load(f)

        # 更新答案
        exam_session['answers'][str(question_index)] = answer
        exam_session['auto_save_count'] += 1
        exam_session['last_save_time'] = datetime.now().isoformat()

        # 保存更新后的会话
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(exam_session, f, ensure_ascii=False, indent=2)

        return jsonify({'success': True, 'save_count': exam_session['auto_save_count']})

    except Exception as e:
        logger.error(f"保存答案失败: {str(e)}")
        return jsonify({'error': f'保存答案失败: {str(e)}'}), 500

@app.route('/api/submit_exam', methods=['POST'])
def submit_exam():
    """提交考试API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '请求数据格式错误'}), 400

        session_id = data.get('session_id')

        if not session_id:
            return jsonify({'error': '缺少会话ID'}), 400

        # 加载考试会话
        session_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}.json")
        if not os.path.exists(session_file):
            return jsonify({'error': '考试会话不存在'}), 404

        with open(session_file, 'r', encoding='utf-8') as f:
            exam_session = json.load(f)

        # 计算得分
        score_result = calculate_exam_score(exam_session['exam_data'], exam_session['answers'])

        # 更新考试会话状态
        exam_session['status'] = 'completed'
        exam_session['end_time'] = datetime.now().isoformat()
        exam_session['score_result'] = score_result

        # 保存最终结果
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(exam_session, f, ensure_ascii=False, indent=2)

        # 保存到考试记录目录
        records_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'exam_records')
        os.makedirs(records_dir, exist_ok=True)

        record_file = os.path.join(records_dir, f"{session_id}_result.json")
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(exam_session, f, ensure_ascii=False, indent=2)

        logger.info(f"考试已提交: {session_id}, 得分: {score_result['total_score']}/{score_result['full_score']}")

        return jsonify({
            'success': True,
            'score_result': score_result,
            'session_data': exam_session
        })

    except Exception as e:
        logger.error(f"提交考试失败: {str(e)}")
        return jsonify({'error': f'提交考试失败: {str(e)}'}), 500

def calculate_exam_score(exam_data, answers):
    """计算考试得分"""
    try:
        questions = exam_data.get('questions', [])
        total_score = 0
        full_score = 0
        question_results = []

        for i, question in enumerate(questions):
            question_score = question.get('score', 1)
            full_score += question_score

            user_answer = answers.get(str(i), '')
            correct_answer = question.get('answer', '')

            # 根据题型计算得分
            if question.get('type') == 'choice':
                # 选择题：用户答案是字母，正确答案是索引
                is_correct = False

                if isinstance(correct_answer, int):
                    # 正确答案是数字索引，用户答案是字母
                    if user_answer and str(user_answer).strip().upper() in ['A', 'B', 'C', 'D', 'E', 'F']:
                        user_index = ord(str(user_answer).strip().upper()) - ord('A')
                        is_correct = user_index == correct_answer
                    else:
                        is_correct = False
                else:
                    # 兼容旧格式：正确答案是字母或文本
                    if str(user_answer).strip().upper() in ['A', 'B', 'C', 'D', 'E', 'F']:
                        # 用户答案是字母，需要转换为文本进行比较
                        options = question.get('options', [])
                        user_index = ord(str(user_answer).strip().upper()) - ord('A')
                        if 0 <= user_index < len(options):
                            user_text = options[user_index]
                            is_correct = user_text.strip() == str(correct_answer).strip()
                        else:
                            is_correct = False
                    else:
                        # 直接文本比较
                        is_correct = str(user_answer).strip() == str(correct_answer).strip()

                earned_score = question_score if is_correct else 0
            elif question.get('type') == 'judge':
                # 判断题：处理布尔值和字母的转换
                if isinstance(correct_answer, bool):
                    if user_answer.upper() == 'A':
                        user_bool = True
                    elif user_answer.upper() == 'B':
                        user_bool = False
                    else:
                        user_bool = None
                    is_correct = user_bool == correct_answer
                else:
                    is_correct = str(user_answer).strip().upper() == str(correct_answer).strip().upper()
                earned_score = question_score if is_correct else 0
            else:
                # 主观题：暂时给满分，可以后续人工评分
                is_correct = bool(user_answer.strip()) if user_answer else False
                earned_score = question_score if is_correct else 0

            total_score += earned_score

            # 格式化显示答案
            display_correct_answer = correct_answer
            display_user_answer = user_answer

            if question.get('type') == 'choice':
                # 选择题：将索引转换为字母显示
                if isinstance(correct_answer, int):
                    display_correct_answer = chr(65 + correct_answer) if 0 <= correct_answer <= 5 else str(correct_answer)
                # 用户答案已经是字母格式，保持不变

            elif question.get('type') == 'judge':
                # 判断题：将布尔值转换为中文显示
                if isinstance(correct_answer, bool):
                    display_correct_answer = "正确" if correct_answer else "错误"
                # 将用户的字母答案转换为中文
                if user_answer == 'A':
                    display_user_answer = "正确"
                elif user_answer == 'B':
                    display_user_answer = "错误"
                elif not user_answer:
                    display_user_answer = "未作答"

            question_results.append({
                'question_index': i,
                'question': question.get('question', ''),
                'user_answer': display_user_answer,
                'correct_answer': display_correct_answer,
                'is_correct': is_correct,
                'earned_score': earned_score,
                'full_score': question_score,
                'question_type': question.get('type', 'unknown')
            })

        return {
            'total_score': total_score,
            'full_score': full_score,
            'percentage': round((total_score / full_score * 100) if full_score > 0 else 0, 2),
            'question_results': question_results
        }

    except Exception as e:
        logger.error(f"计算考试得分失败: {str(e)}")
        return {
            'total_score': 0,
            'full_score': 0,
            'percentage': 0,
            'question_results': [],
            'error': str(e)
        }

@app.route('/api/exam_records', methods=['GET'])
def get_exam_records():
    """获取考试记录API"""
    try:
        records_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'exam_records')
        if not os.path.exists(records_dir):
            return jsonify({'records': []})

        records = []
        for filename in os.listdir(records_dir):
            if filename.endswith('_result.json'):
                try:
                    filepath = os.path.join(records_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        record = json.load(f)

                    # 提取关键信息
                    summary = {
                        'session_id': record.get('session_id', ''),
                        'student_name': record.get('student_name', '匿名'),
                        'exam_title': record.get('exam_data', {}).get('title', '未知试卷'),
                        'subject': record.get('exam_data', {}).get('subject', '未知学科'),
                        'start_time': record.get('start_time', ''),
                        'end_time': record.get('end_time', ''),
                        'status': record.get('status', 'unknown'),
                        'total_score': record.get('score_result', {}).get('total_score', 0),
                        'full_score': record.get('score_result', {}).get('full_score', 0),
                        'percentage': record.get('score_result', {}).get('percentage', 0)
                    }
                    records.append(summary)

                except Exception as e:
                    logger.error(f"读取考试记录文件 {filename} 失败: {str(e)}")
                    continue

        # 按时间倒序排列
        records.sort(key=lambda x: x.get('end_time', ''), reverse=True)

        return jsonify({'records': records})

    except Exception as e:
        logger.error(f"获取考试记录失败: {str(e)}")
        return jsonify({'error': f'获取考试记录失败: {str(e)}'}), 500

@app.route('/api/exam_record/<session_id>', methods=['GET'])
def get_exam_record_detail(session_id):
    """获取考试记录详情API"""
    try:
        records_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'exam_records')
        record_file = os.path.join(records_dir, f"{session_id}_result.json")

        if not os.path.exists(record_file):
            return jsonify({'error': '考试记录不存在'}), 404

        with open(record_file, 'r', encoding='utf-8') as f:
            record = json.load(f)

        return jsonify(record)

    except Exception as e:
        logger.error(f"获取考试记录详情失败: {str(e)}")
        return jsonify({'error': f'获取考试记录详情失败: {str(e)}'}), 500

@app.route('/api/export_exam', methods=['POST'])
def export_exam():
    data = request.get_json()
    exam_data = data.get('exam')

    if not exam_data:
        return jsonify({'error': '缺少试卷数据'}), 400
    
    try:
        # 生成试卷文本
        content = []
        content.append(f"{exam_data['title']}\n")
        content.append(f"总分：{exam_data['totalScore']}分  时间：{exam_data['duration']}\n")
        content.append("=" * 50 + "\n\n")
        
        for i, section in enumerate(exam_data['questions'], 1):
            content.append(f"{i}. {section['type']}（{section['score']}分）\n")
            for j, item in enumerate(section['items'], 1):
                content.append(f"{j}. {item['content']}\n")
                if 'options' in item and item['options']:
                    for k, opt in enumerate(item['options']):
                        content.append(f"   {chr(65+k)}. {opt}\n")
                content.append("\n")
            content.append("\n")
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
            f.write(''.join(content))
            temp_path = f.name
        
        return send_file(
            temp_path,
            mimetype='text/plain',
            as_attachment=True,
            download_name=f"试卷_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
    except Exception as e:
        logger.error(f"导出试卷失败: {str(e)}")
        return jsonify({'error': f'导出试卷失败: {str(e)}'}), 500

@app.route('/api/review_exam', methods=['POST'])
def review_exam():
    subject = request.form.get('subject', '')
    if not subject or subject not in get_available_subjects():
        return jsonify({'error': '请选择有效的学科'}), 400
    
    if 'file' not in request.files:
        return jsonify({'error': '未上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # 规范化上传路径
        upload_folder = os.path.abspath(app.config['UPLOAD_FOLDER'])
        filepath = os.path.abspath(os.path.join(upload_folder, filename))
        
        # 检查规范化后的路径是否在允许的目录内
        if not filepath.startswith(upload_folder):
            logger.error(f"检测到路径穿越攻击尝试: {filepath}")
            return jsonify({'error': '非法文件路径'}), 400
            
        try:
            # 确保上传目录存在
            os.makedirs(upload_folder, exist_ok=True)
            
            # 保存文件
            file.save(filepath)
            
            # 读取试卷内容
            with open(filepath, 'r', encoding='utf-8') as f:
                exam_content = f.read()
            
            # 解析试卷内容
            exam_data = exam_parser.parse_exam_content(exam_content)
            
            # 加载知识库
            knowledge_base = load_knowledge_base(subject)
            
            # 批改每道题目
            total_score = 0
            knowledge_points = {}
            
            for question in exam_data['questions']:
                review_result = review_exam_answer(question, question['answer'], knowledge_base)
                question['score'] = review_result['score']
                question['comment'] = review_result['comment']
                total_score += review_result['score']
                
                # 合并知识点掌握度
                for point, score in review_result['knowledge_points'].items():
                    if point in knowledge_points:
                        knowledge_points[point] = (knowledge_points[point] + score) / 2
                    else:
                        knowledge_points[point] = score
            
            # 生成学习建议
            learning_suggestions = generate_learning_suggestions(knowledge_points)
            
            # 生成总评
            overall_comment = f"""
            本次考试总得分 {total_score}/{exam_data['exam_info']['full_score']} 分。
            """
            
            response_data = {
                'exam_info': exam_data['exam_info'],
                'total_score': total_score,
                'full_score': exam_data['exam_info']['full_score'],
                'questions': exam_data['questions'],
                'knowledge_analysis': knowledge_points,
                'learning_suggestions': learning_suggestions,
                'overall_comment': overall_comment
            }
            
            return jsonify(response_data)
            
        except Exception as e:
            logger.error(f"处理试卷失败: {str(e)}")
            return jsonify({'error': f'处理试卷时出错: {str(e)}'}), 500
        finally:
            # 清理上传的文件
            try:
                if os.path.exists(filepath):
                    os.unlink(filepath)
            except Exception as e:
                logger.error(f"清理上传文件失败: {str(e)}")

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({'error': '缺少反馈内容'}), 400
    
    try:
        success = feedback_manager.add_feedback(data)
        if success:
            logger.info(f"收到新的反馈: {data.get('content')[:100]}...")
            return jsonify({'message': '感谢您的反馈！'})
        else:
            return jsonify({'error': '保存反馈失败'}), 500
    except Exception as e:
        logger.error(f"处理反馈失败: {str(e)}")
        return jsonify({'error': f'处理反馈时出错: {str(e)}'}), 500

@app.route('/api/chapters')
@performance_monitor
def get_chapters():
    """提供章节列表 API - 性能优化版本"""
    subject = request.args.get('subject', '')
    if not subject:
        logger.error("API 请求 /api/chapters 时缺少 subject 参数")
        return jsonify({'error': '缺少学科参数'}), 400

    # 检查内存缓存
    cache_key = f"chapters_{subject}"
    cached_chapters = memory_cache.get(cache_key)
    if cached_chapters:
        return jsonify({'chapters': cached_chapters, 'cached': True})

    available_subjects = get_available_subjects()
    if subject not in available_subjects:
        logger.error(f"API 请求 /api/chapters 时，学科 {subject} 不存在。可用学科: {available_subjects}")
        return jsonify({'error': f'学科 {subject} 不存在'}), 400

    try:
        knowledge_base = load_knowledge_base(subject)
        if not knowledge_base:
            logger.error(f"API 请求 /api/chapters 时，无法加载学科 {subject} 的知识库")
            return jsonify({'error': f'无法加载学科 {subject} 的知识库'}), 500

        chapters_data = [
            {'id': i, 'title': title}
            for i, title in enumerate(knowledge_base.get('章节', {}).keys())
        ]

        if not chapters_data:
            logger.warning(f"API 请求 /api/chapters 时，学科 {subject} 的章节列表为空")

        # 缓存结果
        memory_cache.set(cache_key, chapters_data, ttl=600)  # 10分钟缓存

        return jsonify({'chapters': chapters_data, 'cached': False})
    except Exception as e:
        logger.error(f"API 请求 /api/chapters 时发生错误: {str(e)}")
        return jsonify({'error': f'加载章节列表失败: {str(e)}'}), 500

@app.route('/api/concepts')
def get_concepts():
    """根据章节名提供知识点列表 API"""
    subject = request.args.get('subject', '')
    chapter_name = request.args.get('chapter')
    
    if not subject or subject not in get_available_subjects():
        return jsonify({'error': '请选择有效的学科'}), 400
        
    if not chapter_name:
        return jsonify({'error': '缺少章节参数'}), 400
        
    try:
        knowledge_base = load_knowledge_base(subject)
        chapter_data = knowledge_base.get('章节', {}).get(chapter_name)
        if not chapter_data:
            logger.warning(f"API 请求 /api/concepts 时未找到章节: {chapter_name}")
            return jsonify({'mainConcepts': [], 'mainContents': []})

        return jsonify({
            'mainConcepts': chapter_data.get('mainConcepts', []),
            'mainContents': chapter_data.get('mainContents', [])
        })
    except Exception as e:
        logger.error(f"API /api/concepts 失败 (章节: {chapter_name}): {str(e)}")
        return jsonify({'error': '无法加载知识点列表', 'details': str(e)}), 500

@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if request.method == 'POST':
        # ... existing code ...
        if 'ai_model' in settings:
            ai_service.update_settings()
        # ... existing code ...
    subjects = get_available_subjects()
    settings = settings_manager.load_settings()
    return render_template('settings.html',
                         subjects=subjects,
                         settings=settings)

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """获取系统设置"""
    try:
        settings = settings_manager.load_settings()
        ai_model_settings = settings.get('ai_model', {})
        return jsonify({
            'ai_model': ai_model_settings.get('type', 'ollama'),
            'model_name': ai_model_settings.get('model_name', ''),
            'api_key': ai_model_settings.get('api_key', '')
        })
    except Exception as e:
        logger.error(f"获取设置失败: {str(e)}")
        return jsonify({'error': f'获取设置时出错: {str(e)}'}), 500

@app.route('/api/settings/update', methods=['POST'])
def update_settings():
    """更新系统设置"""
    try:
        new_settings = request.get_json()
        if not new_settings:
            return jsonify({'error': '无效的请求数据'}), 400

        # 加载现有设置
        current_settings = settings_manager.load_settings()

        # 更新AI模型设置
        if 'ai_model' in new_settings or 'model_name' in new_settings or 'api_key' in new_settings:
            ai_model_settings = current_settings.get('ai_model', {})

            # 更新AI模型相关设置
            if 'ai_model' in new_settings:
                ai_model_settings['type'] = new_settings['ai_model']
            if 'model_name' in new_settings:
                ai_model_settings['model_name'] = new_settings['model_name']
            if 'api_key' in new_settings:
                ai_model_settings['api_key'] = new_settings['api_key']

            current_settings['ai_model'] = ai_model_settings

        # 验证更新后的完整设置
        is_valid, message = settings_manager.validate_settings(current_settings)
        if not is_valid:
            return jsonify({'error': message}), 400

        # 保存设置
        if settings_manager.save_settings(current_settings):
            # 更新AI服务设置
            ai_service.update_settings()

            # 清除知识库缓存
            clear_config_cache()

            logger.info("系统设置已更新")
            return jsonify({'message': '设置已成功保存！'})
        else:
            return jsonify({'error': '保存设置时发生内部错误'}), 500
    except Exception as e:
        logger.error(f"更新设置失败: {str(e)}")
        return jsonify({'error': f'更新设置时出错: {str(e)}'}), 500

@app.route('/api/generate_chapter', methods=['POST'])
def generate_chapter():
    """生成整个章节的内容"""
    try:
        data = request.get_json()
        subject = data.get('subject', '')
        chapter = data.get('chapter')
        
        if not subject or subject not in get_available_subjects():
            return jsonify({'error': '请选择有效的学科'}), 400
            
        if not chapter:
            return jsonify({'error': '缺少章节参数'}), 400
        
        knowledge_base = load_knowledge_base(subject)
        chapter_data = knowledge_base.get('章节', {}).get(chapter)
        if not chapter_data:
            return jsonify({'error': '未找到指定章节'}), 404
        
        results = generate_chapter_content(chapter, chapter_data)
        
        return jsonify({
            'message': '章节内容生成完成',
            'results': results
        })
    except Exception as e:
        logger.error(f"生成章节内容失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_all', methods=['POST'])
def generate_all():
    """生成所有章节的内容"""
    try:
        data = request.get_json()
        subject = data.get('subject', '')
        
        if not subject or subject not in get_available_subjects():
            return jsonify({'error': '请选择有效的学科'}), 400
            
        knowledge_base = load_knowledge_base(subject)
        results = {}
        
        for chapter in knowledge_base.get('章节', {}).keys():
            chapter_data = knowledge_base['章节'][chapter]
            results[chapter] = generate_chapter_content(chapter, chapter_data)
        
        return jsonify({
            'message': '所有内容生成完成',
            'results': results
        })
    except Exception as e:
        logger.error(f"生成所有内容失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/subjects', methods=['GET'])
def get_subjects():
    """获取所有可用学科"""
    return jsonify(get_available_subjects())

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """清除缓存"""
    try:
        # 清除内存缓存
        memory_cache.clear()

        # 清除配置缓存
        clear_config_cache()

        return jsonify({'message': '缓存已清除'})
    except Exception as e:
        logger.error(f"清除缓存失败: {str(e)}")
        return jsonify({'error': f'清除缓存失败: {str(e)}'}), 500

@app.route('/test_effects')
def test_effects():
    """前端特效测试页面"""
    return send_file('test_effects.html')

@app.route('/offline')
def offline():
    """离线页面"""
    return render_template('offline.html')

@app.route('/offline.html')
def offline_html():
    """离线页面 - 兼容Service Worker"""
    return render_template('offline.html')

@app.route('/performance-test')
def performance_test():
    """性能测试页面"""
    return render_template('performance-test.html')

@app.route('/component-showcase')
def component_showcase():
    """组件展示页面 - 重构版设计系统"""
    return render_template('component-showcase.html')

@app.route('/api/subjects', methods=['POST'])
def add_subject():
    """添加新学科"""
    try:
        subject_name = request.json.get('name')
        if not subject_name:
            return jsonify({'error': '学科名称不能为空'}), 400

        logger.info(f"开始添加学科: {subject_name}")

        # 创建学科目录
        subject_path = get_subject_config_path(subject_name)
        os.makedirs(subject_path, exist_ok=True)

        # 获取文件路径（不自动创建文件）
        kb_path = os.path.join(subject_path, 'knowledgebase.json')
        tm_path = os.path.join(subject_path, 'testmodel.json')

        # 使用AI生成知识库内容
        if not os.path.exists(kb_path) or not os.path.exists(tm_path):
            logger.info(f"为学科 '{subject_name}' 生成AI知识库内容")

            try:
                # 创建生成器实例
                logger.info(f"创建知识库生成器实例")
                generator = KnowledgeGenerator(ai_service)

                # 生成知识库和考试模板
                logger.info(f"开始为学科 '{subject_name}' 生成AI知识库")
                knowledge_base, test_model = generator.generate_knowledge_base(subject_name)
                logger.info(f"AI知识库生成完成，章节数: {len(knowledge_base.get('章节', {}))}")

                # 保存知识库文件
                if not os.path.exists(kb_path):
                    with open(kb_path, 'w', encoding='utf-8') as f:
                        json.dump(knowledge_base, f, ensure_ascii=False, indent=2)
                    logger.info(f"知识库文件已生成: {kb_path}")

                # 保存考试模板文件
                if not os.path.exists(tm_path):
                    with open(tm_path, 'w', encoding='utf-8') as f:
                        json.dump(test_model, f, ensure_ascii=False, indent=2)
                    logger.info(f"考试模板文件已生成: {tm_path}")

                logger.info(f"学科 '{subject_name}' AI内容生成完成")

            except Exception as ai_error:
                logger.error(f"AI生成内容失败，使用默认内容: {str(ai_error)}")
                logger.error(f"AI生成异常详情: {type(ai_error).__name__}: {ai_error}")
                import traceback
                logger.error(f"AI生成异常堆栈: {traceback.format_exc()}")

                # AI生成失败时使用默认内容
                if not os.path.exists(kb_path):
                    default_kb = {
                        "科目": subject_name,
                        "章节": {
                            "第一章 基础概念": {
                                "mainConcepts": [
                                    f"{subject_name}的定义",
                                    f"{subject_name}的发展历史",
                                    f"{subject_name}的基本原理",
                                    f"{subject_name}的研究方法"
                                ],
                                "mainContents": [
                                    f"{subject_name}是一门重要的学科",
                                    f"{subject_name}的发展经历了多个阶段",
                                    f"{subject_name}具有重要的理论价值和实践意义"
                                ]
                            }
                        }
                    }
                    with open(kb_path, 'w', encoding='utf-8') as f:
                        json.dump(default_kb, f, ensure_ascii=False, indent=2)

                if not os.path.exists(tm_path):
                    default_tm = {
                        "考试信息": {
                            "考试名称": f"{subject_name}考试",
                            "总时长": "120分钟",
                            "题型列表": [
                                {
                                    "题型名称": "单项选择题",
                                    "题量": 10,
                                    "总分": 20,
                                    "考查重点": "对基本概念和理论的掌握",
                                    "内容范围": "各章节的基本概念"
                                }
                            ]
                        }
                    }
                    with open(tm_path, 'w', encoding='utf-8') as f:
                        json.dump(default_tm, f, ensure_ascii=False, indent=2)

        clear_config_cache()
        logger.info(f"学科 '{subject_name}' 添加完成")
        return jsonify({'message': '学科添加成功，知识库内容已自动生成'})

    except Exception as e:
        logger.error(f"添加学科失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/subjects/<subject_name>', methods=['DELETE'])
def delete_subject(subject_name):
    """删除学科"""
    try:
        if subject_name not in get_available_subjects():
            return jsonify({'error': '学科不存在'}), 404

        subject_path = get_subject_config_path(subject_name)
        # 删除学科目录及其内容
        import shutil
        shutil.rmtree(subject_path)

        clear_config_cache()
        return jsonify({'message': '学科删除成功'})
    except Exception as e:
        logger.error(f"删除学科失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache_api():
    """清除所有缓存"""
    try:
        # 清除配置缓存
        clear_config_cache()

        # 清除内存缓存
        memory_cache.clear()

        # 清除文件缓存（可选，保留解释缓存可能有用）
        # import shutil
        # if os.path.exists(CACHE_DIR):
        #     shutil.rmtree(CACHE_DIR)
        #     os.makedirs(CACHE_DIR, exist_ok=True)

        logger.info("缓存已清除")
        return jsonify({'message': '缓存已成功清除'})
    except Exception as e:
        logger.error(f"清除缓存失败: {str(e)}")
        return jsonify({'error': f'清除缓存时出错: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True) 