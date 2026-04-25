import os
import json
from datetime import datetime
from dotenv import load_dotenv
from modules import logger

log = logger.get_logger("Dolphin.config")

load_dotenv()

DATE_DIR = "date"
CONFIG_FILE = os.path.join(DATE_DIR, "config.json")

MODEL_REGISTRY = {
    "deepseek-v4-flash": {
        "name": "deepseek-v4-flash",
        "description": "DeepSeek V4 Flash (快速模型)",
        "deprecated": False,
    },
    "deepseek-v4-pro": {
        "name": "deepseek-v4-pro",
        "description": "DeepSeek V4 Pro (高性能模型)",
        "deprecated": False,
    },
    "deepseek-chat": {
        "name": "deepseek-chat",
        "description": "DeepSeek Chat (已废弃，对应 deepseek-v4-flash 非思考模式)",
        "deprecated": True,
        "deprecation_date": "2026-07-24",
        "replacement": "deepseek-v4-flash",
    },
    "deepseek-reasoner": {
        "name": "deepseek-reasoner",
        "description": "DeepSeek Reasoner (已废弃，对应 deepseek-v4-flash 思考模式)",
        "deprecated": True,
        "deprecation_date": "2026-07-24",
        "replacement": "deepseek-v4-flash",
    },
    "deepseek-coder": {
        "name": "deepseek-coder",
        "description": "DeepSeek Coder (已废弃)",
        "deprecated": True,
        "deprecation_date": "2026-07-24",
        "replacement": "deepseek-v4-flash",
    },
}

def get_available_models():
    """获取可用模型列表，返回带有废弃信息的模型列表"""
    models = []
    for model_name, model_info in MODEL_REGISTRY.items():
        models.append(model_info)
    return models

def check_model_deprecation(model_name):
    """检查模型是否已废弃或即将废弃，返回警告信息"""
    if model_name not in MODEL_REGISTRY:
        return None
    
    model_info = MODEL_REGISTRY[model_name]
    if not model_info.get("deprecated"):
        return None
    
    deprecation_date_str = model_info.get("deprecation_date", "")
    replacement = model_info.get("replacement", "")
    
    try:
        deprecation_date = datetime.strptime(deprecation_date_str, "%Y-%m-%d")
        now = datetime.now()
        
        if now >= deprecation_date:
            msg = f"模型 '{model_name}' 已于 {deprecation_date_str} 废弃"
        else:
            days_left = (deprecation_date - now).days
            msg = f"模型 '{model_name}' 将于 {deprecation_date_str} 废弃 (剩余 {days_left} 天)"
        
        if replacement:
            msg += f"，请改用 '{replacement}'"
        return msg
    except (ValueError, TypeError):
        return None

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                log.debug(f"加载配置文件: {CONFIG_FILE}")
                return config_data
        except Exception as e:
            log.error(f"加载配置文件失败: {e}")
    log.debug("使用默认配置")
    return {
        "api_key": os.getenv("QUICKAI_API_KEY", ""),
        "base_url": os.getenv("QUICKAI_BASE_URL", "https://api.deepseek.com"),
        "model": "deepseek-v4-flash",
        "work_directory": "workplace",
        "skills": {}
    }

def save_config(config):
    if not os.path.exists(DATE_DIR):
        os.makedirs(DATE_DIR)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    log.debug(f"保存配置文件: {CONFIG_FILE}")
