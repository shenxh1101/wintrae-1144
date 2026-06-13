import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

HISTORY_DIR = Path.home() / '.doctidy' / 'history'
MAX_HISTORY = 10


def ensure_history_dir():
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def save_operation(operation_type: str, changes: List[Dict], description: str = "") -> str:
    ensure_history_dir()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    history_id = f"{operation_type}_{timestamp}"
    
    history_data = {
        'id': history_id,
        'type': operation_type,
        'timestamp': timestamp,
        'description': description,
        'changes': changes,
        'undone': False
    }
    
    history_file = HISTORY_DIR / f"{history_id}.json"
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2, default=str)
    
    _cleanup_old_history()
    return history_id


def _cleanup_old_history():
    history_files = sorted(HISTORY_DIR.glob('*.json'), reverse=True)
    for old_file in history_files[MAX_HISTORY:]:
        try:
            old_file.unlink()
        except OSError:
            pass


def get_history(limit: int = 10) -> List[Dict]:
    ensure_history_dir()
    history_files = sorted(HISTORY_DIR.glob('*.json'), reverse=True)
    
    histories = []
    for hf in history_files[:limit]:
        try:
            with open(hf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                histories.append(data)
        except (json.JSONDecodeError, IOError):
            continue
    
    return histories


def get_last_operation() -> Optional[Dict]:
    histories = get_history(limit=1)
    if histories:
        return histories[0]
    return None


def undo_operation(history_id: Optional[str] = None) -> Dict:
    if history_id:
        history_file = HISTORY_DIR / f"{history_id}.json"
        if not history_file.exists():
            raise FileNotFoundError(f"未找到操作记录: {history_id}")
    else:
        last_op = None
        for h in get_history(limit=MAX_HISTORY):
            if not h.get('undone'):
                last_op = h
                break
        if not last_op:
            raise ValueError("没有可撤销的操作")
        history_file = HISTORY_DIR / f"{last_op['id']}.json"
    
    with open(history_file, 'r', encoding='utf-8') as f:
        history_data = json.load(f)
    
    if history_data.get('undone'):
        raise ValueError("该操作已被撤销")
    
    results = {
        'success': [],
        'failed': [],
        'skipped': []
    }
    
    for change in reversed(history_data['changes']):
        try:
            if history_data['type'] == 'rename':
                src = change['new_path']
                dst = change['old_path']
                if os.path.exists(src):
                    os.rename(src, dst)
                    results['success'].append(f"{os.path.basename(src)} -> {os.path.basename(dst)}")
                else:
                    results['skipped'].append(f"源文件不存在: {src}")
            
            elif history_data['type'] == 'classify':
                src = change['new_path']
                dst = change['old_path']
                action = change.get('action', 'move')
                if not os.path.exists(src):
                    results['skipped'].append(f"源文件不存在: {src}")
                    continue
                if action == 'copy':
                    try:
                        os.remove(src)
                        results['success'].append(f"删除副本: {os.path.basename(src)}")
                        parent = str(Path(src).parent)
                        try:
                            if Path(parent).exists() and not any(Path(parent).iterdir()):
                                Path(parent).rmdir()
                        except OSError:
                            pass
                    except OSError as e:
                        results['failed'].append(f"删除副本失败 {src}: {str(e)}")
                else:
                    Path(dst).parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(src, dst)
                    results['success'].append(f"{os.path.basename(src)} -> {dst}")
            
            elif history_data['type'] == 'merge':
                merged_file = change['merged_file']
                if os.path.exists(merged_file):
                    os.remove(merged_file)
                    results['success'].append(f"删除合并文件: {os.path.basename(merged_file)}")
                else:
                    results['skipped'].append(f"合并文件不存在: {merged_file}")
        
        except Exception as e:
            results['failed'].append(f"{change.get('old_path', '未知')}: {str(e)}")
    
    history_data['undone'] = True
    history_data['undo_results'] = results
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2, default=str)
    
    return results


def generate_report(
    operation: str,
    files: List[Dict],
    changes: List[Dict],
    duplicates: Optional[Dict] = None,
    missing: Optional[List[str]] = None,
    total_files: Optional[int] = None
) -> Dict:
    count = total_files if total_files is not None else len(files)
    report = {
        'operation': operation,
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_files': count,
            'total_changes': len(changes),
        },
        'changes': changes
    }
    
    if files:
        report['files'] = files
    
    if duplicates:
        report['duplicates'] = {
            'count': len(duplicates),
            'groups': list(duplicates.values())
        }
        report['summary']['duplicate_groups'] = len(duplicates)
        report['summary']['duplicate_files'] = sum(len(g) for g in duplicates.values())
    
    if missing:
        report['missing_attachments'] = missing
        report['summary']['missing_count'] = len(missing)
    
    return report
