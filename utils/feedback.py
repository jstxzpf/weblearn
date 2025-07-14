import json
import os
from filelock import FileLock
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FeedbackManager:
    def __init__(self, feedback_file='data/feedback.json'):
        self.feedback_file = feedback_file
        self.lock_file = f"{self.feedback_file}.lock"
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """确保反馈文件存在"""
        os.makedirs(os.path.dirname(self.feedback_file), exist_ok=True)
        if not os.path.exists(self.feedback_file):
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump({"feedbacks": []}, f, ensure_ascii=False, indent=2)

    def add_feedback(self, feedback_data):
        """添加新的反馈
        Args:
            feedback_data: 反馈数据，包含：
                - module: 模块名称
                - content: 反馈内容
                - type: 反馈类型（建议/问题/其他）
                - contact: 联系方式（可选）
        Returns:
            bool: 是否添加成功
        """
        try:
            lock = FileLock(self.lock_file, timeout=10)
            with lock:
                with open(self.feedback_file, 'r+', encoding='utf-8') as f:
                    feedbacks = json.load(f)
                    feedback_data['timestamp'] = datetime.now().isoformat()
                    feedbacks['feedbacks'].append(feedback_data)
                    
                    f.seek(0)
                    f.truncate()
                    json.dump(feedbacks, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"添加反馈失败: {str(e)}")
            return False

    def get_feedbacks(self, status=None, module=None):
        """获取反馈列表
        Args:
            status: 反馈状态（可选）
            module: 模块名称（可选）
        Returns:
            list: 反馈列表
        """
        try:
            lock = FileLock(self.lock_file, timeout=5)
            with lock:
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    feedbacks = json.load(f)['feedbacks']
                    if status:
                        feedbacks = [f for f in feedbacks if f['status'] == status]
                    if module:
                        feedbacks = [f for f in feedbacks if f['module'] == module]
                    return feedbacks
        except Exception as e:
            logger.error(f"获取反馈失败: {str(e)}")
            return []

    def update_feedback_status(self, feedback_id, new_status):
        """更新反馈状态
        Args:
            feedback_id: 反馈ID
            new_status: 新状态
        Returns:
            bool: 是否更新成功
        """
        try:
            lock = FileLock(self.lock_file, timeout=5)
            with lock:
                with open(self.feedback_file, 'r+', encoding='utf-8') as f:
                    feedbacks = json.load(f)
                    
                    for feedback in feedbacks['feedbacks']:
                        if feedback.get('id') == feedback_id:
                            feedback['status'] = new_status
                            feedback['updated_at'] = datetime.now().isoformat()
                            break
                    
                    f.seek(0)
                    f.truncate()
                    json.dump(feedbacks, f, ensure_ascii=False, indent=2)
                    
            return True
        except Exception as e:
            logger.error(f"更新反馈状态失败: {str(e)}")
            return False 