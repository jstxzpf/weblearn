import logging
import requests
import json
import os
from openai import OpenAI
from config.settings_manager import SettingsManager

class AIService:
    def __init__(self):
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.load_settings()
        self.model_type = self.settings['ai_model']['type']
        self.model_name = self.settings['ai_model']['model_name']
        self.api_key = self.settings['ai_model']['api_key']
        
        # 初始化客户端
        self._initialize_client()

    def _initialize_client(self):
        """初始化AI客户端"""
        if self.model_type == 'aliyun':
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
        elif self.model_type == 'tencent':
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.lkeap.cloud.tencent.com/v1"
            )
        else:
            self.client = None  # Ollama 不需要客户端初始化

    def generate_response(self, prompt):
        """根据配置选择AI模型并获取响应"""
        try:
            if self.model_type == 'ollama':
                response = requests.post(
                    "http://10.132.60.111:11434/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                response.raise_for_status()
                return response.json()["response"]
            elif self.model_type in ['aliyun', 'tencent']:
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {'role': 'user', 'content': prompt}
                    ]
                )
                return completion.choices[0].message.content
            else:
                logging.error(f"不支持的AI模型类型: {self.model_type}")
                return f"不支持的AI模型类型: {self.model_type}"
        except Exception as e:
            logging.error(f"获取AI响应失败: {str(e)}")
            return f"获取AI响应失败: {str(e)}"
    
    def update_settings(self):
        """更新设置"""
        self.settings = self.settings_manager.load_settings()
        self.model_type = self.settings['ai_model']['type']
        self.model_name = self.settings['ai_model']['model_name']
        self.api_key = self.settings['ai_model']['api_key']

        # 重新初始化客户端
        self._initialize_client()