#!/usr/bin/env python3
"""
知识库自动生成模块
"""

import json
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

class KnowledgeGenerator:
    """知识库自动生成器"""
    
    def __init__(self, ai_service):
        self.ai_service = ai_service
    
    def generate_knowledge_base(self, subject_name: str) -> Tuple[Dict, Dict]:
        """
        根据学科名称生成完整的知识库和考试模板
        
        Args:
            subject_name: 学科名称
            
        Returns:
            Tuple[Dict, Dict]: (知识库数据, 考试模板数据)
        """
        try:
            logger.info(f"开始为学科 '{subject_name}' 生成知识库")
            
            # 1. 生成知识库结构
            knowledge_base = self._generate_knowledge_structure(subject_name)
            
            # 2. 生成考试模板
            test_model = self._generate_test_model(subject_name, knowledge_base)
            
            logger.info(f"学科 '{subject_name}' 知识库生成完成")
            return knowledge_base, test_model
            
        except Exception as e:
            logger.error(f"生成知识库失败: {str(e)}")
            # 返回默认内容
            return self._get_default_knowledge_base(subject_name), self._get_default_test_model(subject_name)
    
    def _generate_knowledge_structure(self, subject_name: str) -> Dict:
        """生成知识库结构"""
        logger.info(f"开始为学科 '{subject_name}' 生成知识库结构")
        prompt = self._create_knowledge_prompt(subject_name)
        logger.debug(f"生成的提示词长度: {len(prompt)}")

        try:
            logger.info(f"直接调用Ollama API生成知识库内容")

            # 直接调用Ollama API
            import requests
            response = requests.post(
                'http://10.132.60.111:11434/api/generate',
                json={
                    'model': 'modelscope.cn/Qwen/Qwen2.5-14B-Instruct-GGUF:Q4_K_M',
                    'prompt': prompt,
                    'stream': False
                },
                timeout=120  # 增加超时时间到2分钟
            )

            if response.status_code != 200:
                logger.error(f"Ollama API调用失败: {response.status_code}")
                return self._get_default_knowledge_base(subject_name)

            ai_response = response.json()["response"]
            logger.info(f"AI响应长度: {len(ai_response)}")
            logger.debug(f"AI响应前200字符: {ai_response[:200]}")

            # 尝试解析AI响应为JSON
            knowledge_data = self._parse_ai_response(ai_response, subject_name)

            if knowledge_data and self._validate_knowledge_structure(knowledge_data):
                logger.info(f"AI生成的知识库验证通过，章节数: {len(knowledge_data.get('章节', {}))}")
                return knowledge_data
            else:
                logger.warning(f"AI生成的知识库格式不正确，使用默认内容")
                return self._get_default_knowledge_base(subject_name)

        except Exception as e:
            logger.error(f"AI生成知识库失败: {str(e)}")
            return self._get_default_knowledge_base(subject_name)
    
    def _create_knowledge_prompt(self, subject_name: str) -> str:
        """创建知识库生成的提示词"""
        return f"""请为"{subject_name}"学科生成知识库结构。

要求：
1. 生成6个章节，涵盖核心内容
2. 每章包含3-5个概念和3-4个内容点
3. 内容要专业准确
4. 只输出JSON，不要其他文字

格式：
{{
  "科目": "{subject_name}",
  "章节": {{
    "第一章 基础概念": {{
      "mainConcepts": ["概念1", "概念2", "概念3"],
      "mainContents": ["内容1", "内容2", "内容3"]
    }},
    "第二章 核心功能": {{
      "mainConcepts": ["概念1", "概念2", "概念3"],
      "mainContents": ["内容1", "内容2", "内容3"]
    }}
  }}
}}

请生成完整的6章内容。"""
    
    def _parse_ai_response(self, response: str, subject_name: str) -> Optional[Dict]:
        """解析AI响应为JSON格式"""
        try:
            # 清理响应文本
            response = response.strip()
            logger.debug(f"原始AI响应: {response}")

            # 尝试多种方法提取JSON
            json_str = None

            # 方法1: 直接解析
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass

            # 方法2: 查找完整的JSON对象
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            # 方法3: 使用正则表达式提取JSON
            import re
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.findall(json_pattern, response, re.DOTALL)

            for match in matches:
                try:
                    data = json.loads(match)
                    if isinstance(data, dict) and "科目" in data and "章节" in data:
                        return data
                except json.JSONDecodeError:
                    continue

            # 方法4: 尝试修复常见的JSON错误
            if json_str:
                # 移除可能的尾随逗号
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)

                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            logger.warning("AI响应中未找到有效的JSON格式")
            logger.debug(f"尝试解析的内容: {json_str if json_str else response[:500]}")
            return None

        except Exception as e:
            logger.error(f"处理AI响应失败: {str(e)}")
            return None
    
    def _validate_knowledge_structure(self, data: Dict) -> bool:
        """验证知识库结构是否正确"""
        try:
            # 检查必需字段
            if "科目" not in data or "章节" not in data:
                return False
            
            chapters = data["章节"]
            if not isinstance(chapters, dict) or len(chapters) == 0:
                return False
            
            # 检查每个章节的结构
            for chapter_name, chapter_data in chapters.items():
                if not isinstance(chapter_data, dict):
                    return False
                
                if "mainConcepts" not in chapter_data or "mainContents" not in chapter_data:
                    return False
                
                if not isinstance(chapter_data["mainConcepts"], list) or \
                   not isinstance(chapter_data["mainContents"], list):
                    return False
                
                # 确保有内容
                if len(chapter_data["mainConcepts"]) == 0 or \
                   len(chapter_data["mainContents"]) == 0:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"验证知识库结构失败: {str(e)}")
            return False
    
    def _generate_test_model(self, subject_name: str, knowledge_base: Dict) -> Dict:
        """根据知识库生成考试模板"""
        try:
            chapters = knowledge_base.get("章节", {})
            chapter_count = len(chapters)
            
            # 根据章节数量调整题型配置
            if chapter_count <= 4:
                # 较少章节，题量适中
                question_types = [
                    {
                        "题型名称": "单项选择题",
                        "题量": 15,
                        "总分": 30,
                        "考查重点": "基本概念和理论的掌握",
                        "内容范围": "各章节的基本概念和原理"
                    },
                    {
                        "题型名称": "名词解释",
                        "题量": 5,
                        "总分": 20,
                        "考查重点": "重要概念的准确理解",
                        "内容范围": "核心概念和专业术语"
                    },
                    {
                        "题型名称": "简答题",
                        "题量": 4,
                        "总分": 30,
                        "考查重点": "理论知识的综合运用",
                        "内容范围": "各章节的主要内容和方法"
                    },
                    {
                        "题型名称": "论述题",
                        "题量": 2,
                        "总分": 20,
                        "考查重点": "综合分析和应用能力",
                        "内容范围": "跨章节的综合性问题"
                    }
                ]
            else:
                # 较多章节，增加题量
                question_types = [
                    {
                        "题型名称": "单项选择题",
                        "题量": 20,
                        "总分": 40,
                        "考查重点": "基本概念和理论的掌握",
                        "内容范围": "各章节的基本概念和原理"
                    },
                    {
                        "题型名称": "名词解释",
                        "题量": 6,
                        "总分": 18,
                        "考查重点": "重要概念的准确理解",
                        "内容范围": "核心概念和专业术语"
                    },
                    {
                        "题型名称": "简答题",
                        "题量": 5,
                        "总分": 25,
                        "考查重点": "理论知识的综合运用",
                        "内容范围": "各章节的主要内容和方法"
                    },
                    {
                        "题型名称": "综合应用题",
                        "题量": 2,
                        "总分": 17,
                        "考查重点": "综合分析和实际应用能力",
                        "内容范围": "理论联系实际的综合性问题"
                    }
                ]
            
            return {
                "考试信息": {
                    "考试名称": f"{subject_name}期末考试",
                    "总时长": "120分钟",
                    "题型列表": question_types
                }
            }
            
        except Exception as e:
            logger.error(f"生成考试模板失败: {str(e)}")
            return self._get_default_test_model(subject_name)
    
    def _get_default_knowledge_base(self, subject_name: str) -> Dict:
        """获取默认知识库内容"""
        return {
            "科目": subject_name,
            "章节": {
                "第一章 基础概念": {
                    "mainConcepts": [
                        f"{subject_name}的定义",
                        f"{subject_name}的发展历史",
                        f"{subject_name}的基本原理",
                        f"{subject_name}的研究方法",
                        f"{subject_name}的应用领域"
                    ],
                    "mainContents": [
                        f"{subject_name}是一门研究...的学科",
                        f"{subject_name}的发展经历了...等阶段",
                        f"{subject_name}的基本原理包括...",
                        f"{subject_name}的主要研究方法有..."
                    ]
                },
                "第二章 理论基础": {
                    "mainConcepts": [
                        "理论框架",
                        "核心理论",
                        "基本假设",
                        "理论模型",
                        "理论应用"
                    ],
                    "mainContents": [
                        f"{subject_name}的理论框架构成",
                        f"{subject_name}的核心理论体系",
                        f"{subject_name}的基本假设条件",
                        f"{subject_name}的理论模型建构"
                    ]
                }
            }
        }
    
    def _get_default_test_model(self, subject_name: str) -> Dict:
        """获取默认考试模板"""
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
                    },
                    {
                        "题型名称": "简答题",
                        "题量": 4,
                        "总分": 40,
                        "考查重点": "理论知识的理解和应用",
                        "内容范围": "各章节的主要内容"
                    },
                    {
                        "题型名称": "论述题",
                        "题量": 2,
                        "总分": 40,
                        "考查重点": "综合分析和论述能力",
                        "内容范围": "跨章节的综合性问题"
                    }
                ]
            }
        }
