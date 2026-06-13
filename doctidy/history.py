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
    ensure_history_dir()
    history_file = _resolve_history_file(history_id)
    
    with open(history_file, 'r', encoding='utf-8') as f:
        history_data = json.load(f)
    
    if history_data.get('undone'):
        raise ValueError("该操作已被撤销")
    
    results = {'success': [], 'failed': [], 'skipped': []}
    
    for change in reversed(history_data['changes']):
        try:
            status, msg = _execute_undo_change(history_data['type'], change)
            results[status].append(msg)
        except Exception as e:
            results['failed'].append(f"{change.get('old_path', '未知')}: {str(e)}")
    
    history_data['undone'] = True
    history_data['undo_results'] = results
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2, default=str)
    
    return results


def _resolve_history_file(history_id: Optional[str]) -> Path:
    if history_id:
        history_file = HISTORY_DIR / f"{history_id}.json"
        if not history_file.exists():
            raise FileNotFoundError(f"未找到操作记录: {history_id}")
        return history_file
    
    for h in get_history(limit=MAX_HISTORY):
        if not h.get('undone'):
            return HISTORY_DIR / f"{h['id']}.json"
    
    raise ValueError("没有可撤销的操作")


def _describe_undo_change(op_type: str, change: Dict) -> str:
    if op_type == 'rename':
        return f"{change.get('new_name', '')} → {change.get('old_name', '')}"
    elif op_type == 'classify':
        action = change.get('action', 'move')
        cat = change.get('category', '')
        if action == 'copy':
            return f"删除副本: {change.get('old_name', '')} (分类: {cat})"
        else:
            return f"移回: [{cat}]{change.get('old_name', '')} → 原位"
    elif op_type == 'merge':
        return f"删除合并文件: {os.path.basename(change.get('merged_file', ''))}"
    return str(change)


def _execute_undo_change(op_type: str, change: Dict) -> Dict:
    if op_type == 'rename':
        src = change['new_path']
        dst = change['old_path']
        if os.path.exists(src):
            os.rename(src, dst)
            return ('success', f"{os.path.basename(src)} -> {os.path.basename(dst)}")
        else:
            return ('skipped', f"源文件不存在: {src}")
    
    elif op_type == 'classify':
        src = change['new_path']
        dst = change['old_path']
        action = change.get('action', 'move')
        if not os.path.exists(src):
            return ('skipped', f"源文件不存在: {src}")
        if action == 'copy':
            try:
                os.remove(src)
                parent = str(Path(src).parent)
                try:
                    if Path(parent).exists() and not any(Path(parent).iterdir()):
                        Path(parent).rmdir()
                except OSError:
                    pass
                return ('success', f"删除副本: {os.path.basename(src)}")
            except OSError as e:
                return ('failed', f"删除副本失败 {src}: {str(e)}")
        else:
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            return ('success', f"{os.path.basename(src)} -> {dst}")
    
    elif op_type == 'merge':
        merged_file = change['merged_file']
        if os.path.exists(merged_file):
            os.remove(merged_file)
            return ('success', f"删除合并文件: {os.path.basename(merged_file)}")
        else:
            return ('skipped', f"合并文件不存在: {merged_file}")
    
    return ('skipped', f"未知操作类型: {op_type}")


def preview_undo(history_id: Optional[str] = None) -> Dict:
    ensure_history_dir()
    history_file = _resolve_history_file(history_id)
    
    with open(history_file, 'r', encoding='utf-8') as f:
        history_data = json.load(f)
    
    if history_data.get('undone'):
        raise ValueError("该操作已被撤销")
    
    items = []
    for change in history_data['changes']:
        items.append(_describe_undo_change(history_data['type'], change))
    
    return {
        'id': history_data['id'],
        'type': history_data['type'],
        'timestamp': history_data['timestamp'],
        'description': history_data.get('description', ''),
        'total_changes': len(history_data['changes']),
        'items': items
    }


def undo_partial(history_id: Optional[str], indices: List[int]) -> Dict:
    ensure_history_dir()
    history_file = _resolve_history_file(history_id)
    
    with open(history_file, 'r', encoding='utf-8') as f:
        history_data = json.load(f)
    
    if history_data.get('undone'):
        raise ValueError("该操作已被撤销")
    
    changes = history_data['changes']
    results = {'success': [], 'failed': [], 'skipped': []}
    undone_indices = set()
    
    for idx in sorted(indices, reverse=True):
        adjusted = idx - 1
        if adjusted < 0 or adjusted >= len(changes):
            results['skipped'].append(f"序号 {idx} 超出范围（1-{len(changes)}）")
            continue
        
        change = changes[adjusted]
        try:
            status, msg = _execute_undo_change(history_data['type'], change)
            results[status].append(msg)
            if status == 'success':
                undone_indices.add(adjusted)
        except Exception as e:
            results['failed'].append(f"{change.get('old_path', '未知')}: {str(e)}")
    
    for idx in sorted(undone_indices, reverse=True):
        changes.pop(idx)
    
    if not changes:
        history_data['undone'] = True
        history_data['partial_undo'] = True
    else:
        history_data['partial_undo'] = True
        history_data['partial_undo_remaining'] = len(changes)
    
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
