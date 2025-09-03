import json
import os
import logging
from filelock import FileLock
import requests

logger = logging.getLogger(__name__)

class SettingsManager:
    def __init__(self, settings_file='config/settings.json'):
        self.settings_file = settings_file
        self.lock_file = f'{settings_file}.lock'
        self._ensure_settings_file_exists()

    def _ensure_settings_file_exists(self):
        """确保设置文件存在，如果不存在则创建默认设置"""
        if not os.path.exists(self.settings_file):
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            self.save_settings(self._get_default_settings())

    def _get_default_settings(self):
        """获取默认设置"""
        return {
            "knowledgebase": {
                "path": "data/knowledgebase.json",
                "auto_reload": True,
                "reload_interval": 300
            },
            "api": {
                "host": "0.0.0.0",
                "port": 5000,
                "debug": False
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": "logs/app.log"
            },
            "ai_model": {
                "type": "ollama",
                "api_key": "",
                "model_name": "modelscope.cn/Qwen/Qwen2.5-14B-Instruct-GGUF:Q4_K_M",
                "assistant_domain": "数据库",
                "assistant_style": "教师",
                "enabled_chapters": []
            }
        }

    def load_settings(self):
        """加载系统设置"""
        try:
            lock = FileLock(self.lock_file, timeout=5)
            with lock:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载设置失败: {str(e)}")
            return self._get_default_settings()

    def save_settings(self, settings):
        """保存系统设置"""
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            lock = FileLock(self.lock_file, timeout=10)
            with lock:
                with open(self.settings_file, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"保存设置失败: {str(e)}")
            return False

    def update_settings(self, new_settings):
        """更新部分设置"""
        current_settings = self.load_settings()
        # 递归更新设置
        def update_dict(d, u):
            for k, v in u.items():
                if isinstance(v, dict):
                    d[k] = update_dict(d.get(k, {}), v)
                else:
                    d[k] = v
            return d
        
        updated_settings = update_dict(current_settings, new_settings)
        return self.save_settings(updated_settings)

    def get_available_ollama_models(self):
        """获取可用的Ollama模型列表"""
        try:
            response = requests.get("http://10.132.60.111:11434/api/tags")
            if response.status_code == 200:
                models_data = response.json()
                return [model['name'] for model in models_data.get('models', [])]
            return []
        except Exception as e:
            logger.error(f"获取Ollama模型列表失败: {str(e)}")
            return []

    def validate_settings(self, settings):
        """验证设置是否有效"""
        try:
            # 验证必需的配置项
            required_sections = ['knowledgebase', 'api', 'logging', 'ai_model']
            for section in required_sections:
                if section not in settings:
                    return False, f"缺少必需的配置项: {section}"

            # 验证AI模型设置
            ai_settings = settings.get('ai_model', {})
            if not ai_settings.get('model_name'):
                return False, "未指定AI模型"

            # 验证端口范围
            api_settings = settings.get('api', {})
            port = api_settings.get('port', 0)
            if not (0 < port < 65536):
                return False, "无效的端口号"

            return True, "设置有效"
        except Exception as e:
            return False, f"验证设置时出错: {str(e)}"

    def get_subject_settings(self, subject_name):
        """获取学科设置"""
        try:
            settings = self.load_settings()
            ai_model_settings = settings.get('ai_model', {})

            # 检查是否是当前配置的学科
            current_domain = ai_model_settings.get('assistant_domain', '')
            if subject_name == current_domain:
                # 返回配置的启用章节
                return {
                    'enabled_chapters': ai_model_settings.get('enabled_chapters', [])
                }
            else:
                # 对于其他学科，默认启用所有章节（返回空列表表示启用所有）
                return {
                    'enabled_chapters': []
                }
        except Exception as e:
            logger.error(f"获取学科 {subject_name} 设置失败: {str(e)}")
            return None