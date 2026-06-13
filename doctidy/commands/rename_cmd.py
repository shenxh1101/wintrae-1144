import os
import re
import click
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from ..utils import (
    scan_directory, extract_date_from_name, extract_number_from_name,
    match_keywords, safe_filename, parse_size, parse_date
)
from ..history import save_operation
from ..config import load_config, get_scan_extensions


def generate_new_name(
    file_info: Dict,
    pattern: str,
    date_source: str = 'auto',
    custom_date: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    counter: int = 0
) -> str:
    name = file_info['stem']
    suffix = file_info['suffix']
    
    if custom_date:
        date_obj = parse_date(custom_date)
    elif date_source == 'auto':
        date_obj = extract_date_from_name(name) or file_info['modified']
    elif date_source == 'modified':
        date_obj = file_info['modified']
    elif date_source == 'created':
        date_obj = file_info['created']
    else:
        date_obj = file_info['modified']
    
    number = extract_number_from_name(name) or ""
    
    matched_keywords = []
    if keywords:
        matched_keywords = match_keywords(name, keywords)
    keyword_str = "_".join(matched_keywords) if matched_keywords else ""
    
    replacements = {
        '{date}': date_obj.strftime('%Y%m%d'),
        '{date-}': date_obj.strftime('%Y-%m-%d'),
        '{date_}': date_obj.strftime('%Y_%m_%d'),
        '{year}': date_obj.strftime('%Y'),
        '{month}': date_obj.strftime('%m'),
        '{day}': date_obj.strftime('%d'),
        '{number}': number or '',
        '{name}': name,
        '{original}': name,
        '{keyword}': keyword_str,
        '{counter}': f"{counter:03d}",
        '{counter2}': f"{counter:02d}",
    }
    
    new_name = pattern
    for key, value in replacements.items():
        new_name = new_name.replace(key, value)
    
    new_name = safe_filename(new_name)
    
    if not new_name:
        new_name = name
    
    return f"{new_name}{suffix}"


def build_target_path(file_info: Dict, new_name: str, output_dir: Optional[str] = None) -> str:
    if output_dir:
        return str(Path(output_dir) / new_name)
    else:
        return str(Path(file_info['parent']) / new_name)


def resolve_conflicts(changes: List[Dict]) -> List[Dict]:
    path_counts: Dict[str, int] = {}
    for change in changes:
        new_path = change['new_path']
        path_counts[new_path] = path_counts.get(new_path, 0) + 1
    
    conflict_paths = {p for p, c in path_counts.items() if c > 1}
    
    if not conflict_paths:
        return changes
    
    path_counters: Dict[str, int] = {}
    for change in changes:
        new_path = change['new_path']
        if new_path in conflict_paths:
            if new_path not in path_counters:
                path_counters[new_path] = 0
            else:
                path_counters[new_path] += 1
                counter = path_counters[new_path]
                
                p = Path(new_path)
                new_name = f"{p.stem}_{counter:02d}{p.suffix}"
                change['new_path'] = str(p.parent / new_name)
    
    return changes


def rename_command(
    directory: str,
    pattern: str,
    recursive: bool = False,
    extensions: Optional[List[str]] = None,
    date_source: str = 'auto',
    custom_date: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
    preview: bool = False,
    min_size: Optional[str] = None,
    max_size: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    date_type: str = 'modified',
    config_path: Optional[str] = None
) -> Dict:
    config = load_config(config_path)
    if extensions is None:
        extensions = get_scan_extensions(config)
    
    min_size_bytes = parse_size(min_size) if min_size else None
    max_size_bytes = parse_size(max_size) if max_size else None
    date_from_dt = parse_date(date_from) if date_from else None
    date_to_dt = parse_date(date_to) if date_to else None
    
    files = scan_directory(
        directory=directory,
        recursive=recursive,
        extensions=extensions,
        min_size=min_size_bytes,
        max_size=max_size_bytes,
        date_from=date_from_dt,
        date_to=date_to_dt,
        date_type=date_type
    )
    
    changes = []
    for i, f in enumerate(files):
        new_name = generate_new_name(
            f, pattern, date_source, custom_date, keywords, i + 1
        )
        new_path = build_target_path(f, new_name, output_dir)
        
        if new_path != f['path']:
            changes.append({
                'old_path': f['path'],
                'old_name': f['name'],
                'new_path': new_path,
                'new_name': new_name
            })
    
    changes = resolve_conflicts(changes)
    
    if not preview and changes:
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        for change in changes:
            try:
                os.rename(change['old_path'], change['new_path'])
                change['success'] = True
            except Exception as e:
                change['success'] = False
                change['error'] = str(e)
        
        save_operation(
            operation_type='rename',
            changes=changes,
            description=f"批量重命名 {len(changes)} 个文件"
        )
    
    return {
        'files': files,
        'changes': changes,
        'total': len(files),
        'renamed': len(changes)
    }


def print_rename_result(result: Dict, preview: bool = False):
    action = "预览" if preview else "重命名"
    
    click.echo("=" * 70)
    click.echo(f"{action}结果: 共扫描 {result['total']} 个文件")
    click.echo(f"将{action} {result['renamed']} 个文件")
    click.echo("=" * 70)
    
    if result['changes']:
        click.echo("")
        for i, change in enumerate(result['changes'], 1):
            old_name = change['old_name']
            new_name = change['new_name']
            old_dir = Path(change['old_path']).parent
            new_dir = Path(change['new_path']).parent
            
            if old_dir == new_dir:
                click.echo(f"{i:3d}. {old_name}")
                click.echo(f"     → {new_name}")
            else:
                click.echo(f"{i:3d}. {change['old_path']}")
                click.echo(f"     → {change['new_path']}")
            
            if 'success' in change and not change['success']:
                click.echo(f"     错误: {change.get('error', '未知错误')}", err=True)
        
        click.echo("")
    
    if preview:
        click.echo("这是预览模式，未执行实际操作。")
        click.echo("去掉 --preview 参数执行实际重命名。")
