import os
import json
from pathlib import Path
from typing import Dict, List, Optional

CONFIG_DIR = Path.home() / '.doctidy'
CONFIG_FILE = CONFIG_DIR / 'config.json'

DEFAULT_CONFIG = {
    "category_rules": {
        "合同": ["合同", "协议", "contract", "agreement", "合作"],
        "报告": ["报告", "report", "分析", "统计", "调研"],
        "发票": ["发票", "invoice", "收据", "账单"],
        "证件": ["证件", "证书", "license", "资质", "执照"],
        "合同附件": ["附件", "attachment", "补充", "附表"]
    },
    "extension_groups": {
        "文档": [".doc", ".docx", ".pdf", ".txt", ".md"],
        "表格": [".xls", ".xlsx", ".csv"],
        "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"],
        "压缩包": [".zip", ".rar", ".7z", ".tar", ".gz"],
        "邮件": [".eml", ".msg"],
        "演示": [".ppt", ".pptx"]
    },
    "main_doc_patterns": [
        "合同", "协议", "Contract", "Agreement",
        "报告", "Report",
        "标书", "投标", "招标",
        "申请书", "申请"
    ],
    "attachment_patterns": [
        {"regex": "附件(\\d*)", "template": "附件{num}"},
        {"regex": "附表(\\d*)", "template": "附表{num}"},
        {"regex": "附图(\\d*)", "template": "附图{num}"},
        {"regex": "附录(\\d*)", "template": "附录{num}"},
        {"regex": "补充(\\d*)", "template": "补充{num}"},
        {"regex": "Attachment[\\s_-]*(\\d*)", "template": "Attachment{num}"},
        {"regex": "Schedule[\\s_-]*(\\d*)", "template": "Schedule{num}"}
    ],
    "scan_extensions": [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".txt", ".csv", ".jpg", ".jpeg", ".png", ".gif", ".bmp",
        ".zip", ".rar", ".7z", ".eml", ".msg"
    ]
}


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config(config_path: Optional[str] = None) -> Dict:
    path = Path(config_path) if config_path else CONFIG_FILE
    
    if not path.exists():
        return _deep_copy(DEFAULT_CONFIG)
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
        return _merge_config(_deep_copy(DEFAULT_CONFIG), user_config)
    except (json.JSONDecodeError, IOError):
        return _deep_copy(DEFAULT_CONFIG)


def save_config(config: Dict, config_path: Optional[str] = None):
    path = Path(config_path) if config_path else CONFIG_FILE
    ensure_config_dir() if not config_path else path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_category_rules(config: Optional[Dict] = None) -> Dict[str, List[str]]:
    cfg = config or load_config()
    return cfg.get('category_rules', DEFAULT_CONFIG['category_rules'])


def get_extension_groups(config: Optional[Dict] = None) -> Dict[str, List[str]]:
    cfg = config or load_config()
    return cfg.get('extension_groups', DEFAULT_CONFIG['extension_groups'])


def get_main_doc_patterns(config: Optional[Dict] = None) -> List[str]:
    cfg = config or load_config()
    return cfg.get('main_doc_patterns', DEFAULT_CONFIG['main_doc_patterns'])


def get_attachment_patterns(config: Optional[Dict] = None) -> List[Dict]:
    cfg = config or load_config()
    return cfg.get('attachment_patterns', DEFAULT_CONFIG['attachment_patterns'])


def get_scan_extensions(config: Optional[Dict] = None) -> List[str]:
    cfg = config or load_config()
    return cfg.get('scan_extensions', DEFAULT_CONFIG['scan_extensions'])


def init_config(config_path: Optional[str] = None) -> str:
    path = Path(config_path) if config_path else CONFIG_FILE
    if path.exists():
        return str(path)
    
    save_config(_deep_copy(DEFAULT_CONFIG), str(path))
    return str(path)


def _deep_copy(d: Dict) -> Dict:
    return json.loads(json.dumps(d))


def _merge_config(base: Dict, override: Dict) -> Dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result
