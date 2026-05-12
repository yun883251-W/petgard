import json
import os
from typing import Dict, Any


class ConfigManager:
    def __init__(self, config_path: str = "config/settings.json"):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "detection": {
                "model_path": "models/yolov8s.pt",
                "confidence_threshold": 0.4,
                "classes": [15, 16],  # 猫狗类别
                "image_size": 640
            },
            "fence": {
                "polygon": [[100, 100], [200, 100], [200, 200], [100, 200]],
                "enable_fencing": True
            },
            "storage": {
                "image_path": "data/images",
                "log_path": "data/logs"
            },
            "performance": {
                "batch_size": 1,
                "use_gpu": True,
                "gpu_device": 0
            },
            "ui": {
                "web_port": 5000,
                "web_host": "0.0.0.0"
            }
        }

        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                # 合并配置，保留默认值对于未定义的项
                for key, value in loaded_config.items():
                    if isinstance(value, dict) and key in default_config:
                        default_config[key].update(value)
                    else:
                        default_config[key] = value

        return default_config

    def save_config(self):
        """保存配置到文件"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def get(self, key: str, default=None):
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split('.')
        config_ref = self.config
        for k in keys[:-1]:
            if k not in config_ref:
                config_ref[k] = {}
            config_ref = config_ref[k]
        config_ref[keys[-1]] = value
        self.save_config()

    def update(self, new_config: Dict[str, Any]):
        """批量更新配置"""
        self._update_dict(self.config, new_config)
        self.save_config()

    def _update_dict(self, old_dict: Dict[str, Any], new_dict: Dict[str, Any]):
        """递归更新字典"""
        for key, value in new_dict.items():
            if key in old_dict and isinstance(old_dict[key], dict) and isinstance(value, dict):
                self._update_dict(old_dict[key], value)
            else:
                old_dict[key] = value