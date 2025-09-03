import os
import logging.config
from flask import current_app

def setup_logging(app):
    # 确保日志目录存在
    log_dir = os.path.join(app.instance_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 日志配置
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'default': {
                'level': 'INFO',
                'formatter': 'standard',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'app.log'),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
                'encoding': 'utf8'
            },
            'error': {
                'level': 'ERROR',
                'formatter': 'standard',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'error.log'),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
                'encoding': 'utf8'
            },
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['default', 'error'],
                'level': 'INFO',
                'propagate': True
            }
        }
    }
    
    # 应用日志配置
    logging.config.dictConfig(logging_config)
    
    # 创建应用级别的logger
    logger = logging.getLogger('dblearning')
    return logger 