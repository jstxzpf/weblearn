import re

class ExamParser:
    def __init__(self):
        # 支持中英文括号的正则表达式
        self.section_pattern = re.compile(r'(\d+)\.\s*(.*?)[\(（](\d+)分[\)）]')
        self.question_pattern = re.compile(r'^(\d+)\.\s*(.*)')
        self.option_pattern = re.compile(r'^\s*([A-D])\.\s*(.*?)$')

    def parse_exam_content(self, content):
        """解析试卷内容
        Args:
            content: 试卷文本内容
        Returns:
            解析后的试卷数据结构
        """
        try:
            lines = content.split('\n')
            exam_data = {
                'exam_info': {},
                'questions': []
            }

            if len(lines) < 2:
                raise ValueError("试卷内容格式不正确")

            # 解析试卷基本信息
            exam_data['exam_info']['title'] = lines[0].strip()
            score_info = re.search(r'总分：(\d+)分', lines[1])
            if score_info:
                exam_data['exam_info']['full_score'] = int(score_info.group(1))
            else:
                exam_data['exam_info']['full_score'] = 100  # 默认值

            current_section = None
            current_questions = []

            # 添加计数器防止无限循环
            line_count = 0
            max_lines = len(lines)

            for line in lines[3:]:  # 跳过标题和分隔线
                line_count += 1
                if line_count > max_lines:
                    break

                line = line.strip()
                if not line:
                    continue
                
                # 尝试匹配题型部分
                section_match = self.section_pattern.match(line)
                if section_match:
                    # 如果有前一个章节，处理它的题目分数并保存
                    if current_section and current_questions:
                        questions_count = len(current_questions)
                        if questions_count > 0:
                            score_per_question = current_section['score'] / questions_count
                            for question in current_questions:
                                question['full_score'] = score_per_question
                                question['score'] = score_per_question
                            exam_data['questions'].extend(current_questions)
                    
                    # 开始新章节
                    current_section = {
                        'type': section_match.group(2),
                        'score': int(section_match.group(3))
                    }
                    current_questions = []
                    continue
                
                # 尝试匹配题目
                question_match = self.question_pattern.match(line)
                if question_match and current_section:
                    current_questions.append({
                        'content': question_match.group(2),
                        'options': [],
                        'answer': '',
                        'score': 0,  # 临时分数，稍后根据题目数量计算
                        'full_score': 0  # 原始满分，稍后设置
                    })
                    continue

                # 尝试匹配选项
                option_match = self.option_pattern.match(line)
                if option_match and current_questions:
                    current_questions[-1]['options'].append(option_match.group(2))
                    continue
                
                # 如果是答案部分
                if line.startswith('答：') and current_questions:
                    current_questions[-1]['answer'] = line[2:].strip()
            
            # 处理最后一个章节的题目分数
            if current_section and current_questions:
                questions_count = len(current_questions)
                if questions_count > 0:
                    score_per_question = current_section['score'] / questions_count
                    for question in current_questions:
                        question['full_score'] = score_per_question
                        question['score'] = score_per_question
                    exam_data['questions'].extend(current_questions)
            
            # 更新题目总数
            exam_data['exam_info']['question_count'] = len(exam_data['questions'])
            
            return exam_data
            
        except Exception as e:
            raise ValueError(f"试卷解析失败: {str(e)}")

    def validate_exam_format(self, content):
        """验证试卷格式是否正确
        Args:
            content: 试卷文本内容
        Returns:
            bool: 格式是否正确
        """
        try:
            lines = content.split('\n')
            
            # 检查基本结构
            if len(lines) < 4:  # 至少需要标题、分数信息、分隔线和一道题目
                return False
            
            # 检查标题
            if not lines[0].strip():
                return False
            
            # 检查分数信息
            if not re.search(r'总分：\d+分', lines[1]):
                return False
            
            # 检查是否包含题目部分
            has_section = False
            for line in lines[3:]:
                if self.section_pattern.match(line):
                    has_section = True
                    break
            
            return has_section
            
        except Exception:
            return False 