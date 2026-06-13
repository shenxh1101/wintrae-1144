import os
import shutil
import click
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from ..utils import (
    scan_directory, extract_date_from_name, match_keywords,
    safe_filename, parse_size, parse_date, format_size
)
from ..history import save_operation
from ..config import load_config, get_category_rules, get_extension_groups


def build_rules(rules_file: Optional[str] = None, 
                custom_rules: Optional[List[str]] = None,
                config_path: Optional[str] = None) -> Dict[str, List[str]]:
    config = load_config(config_path) if config_path else None
    rules = get_category_rules(config)
    
    if rules_file and os.path.exists(rules_file):
        try:
            with open(rules_file, 'r', encoding='utf-8') as f:
                file_rules = json.load(f)
                if isinstance(file_rules, dict):
                    rules.update(file_rules)
        except Exception as e:
            click.echo(f"警告: 无法读取规则文件 {rules_file}: {e}", err=True)
    
    if custom_rules:
        for rule in custom_rules:
            if ':' in rule:
                category, keywords_str = rule.split(':', 1)
                keywords = [k.strip() for k in keywords_str.split(',')]
                rules[category.strip()] = keywords
    
    return rules


def classify_by_extension(file_info: Dict, config_path: Optional[str] = None) -> Optional[str]:
    ext = file_info['extension']
    config = load_config(config_path) if config_path else None
    ext_groups = get_extension_groups(config)
    
    for category, exts in ext_groups.items():
        if ext in exts:
            return category
    return None


def classify_by_date(file_info: Dict, date_format: str = '%Y-%m') -> str:
    date_obj = extract_date_from_name(file_info['name']) or file_info['modified']
    return date_obj.strftime(date_format)


def determine_category(file_info: Dict, rules: Dict[str, List[str]], 
                       method: str = 'keyword',
                       config_path: Optional[str] = None) -> Optional[str]:
    name = file_info['name']
    
    if method in ('keyword', 'all'):
        for category, keywords in rules.items():
            matched = match_keywords(name, keywords)
            if matched:
                return category
    
    if method in ('extension', 'all'):
        ext_cat = classify_by_extension(file_info, config_path)
        if ext_cat:
            return ext_cat
    
    if method in ('date', 'all'):
        return classify_by_date(file_info)
    
    return None


def classify_command(
    directory: str,
    output_dir: str,
    recursive: bool = False,
    extensions: Optional[List[str]] = None,
    method: str = 'keyword',
    rules_file: Optional[str] = None,
    rules: Optional[List[str]] = None,
    date_format: str = '%Y-%m',
    copy: bool = False,
    preview: bool = False,
    min_size: Optional[str] = None,
    max_size: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    date_type: str = 'modified',
    config_path: Optional[str] = None
) -> Dict:
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
    
    category_rules = build_rules(rules_file, rules, config_path)
    
    if method == 'date':
        category_rules = {}
    
    changes = []
    category_stats: Dict[str, int] = {}
    
    for f in files:
        if method == 'date':
            category = classify_by_date(f, date_format)
        else:
            category = determine_category(f, category_rules, method, config_path)
        
        if category is None:
            category = '未分类'
        
        category = safe_filename(category)
        target_dir = Path(output_dir) / category
        target_path = target_dir / f['name']
        
        changes.append({
            'old_path': f['path'],
            'old_name': f['name'],
            'new_path': str(target_path),
            'new_name': f['name'],
            'category': category,
            'action': 'copy' if copy else 'move'
        })
        
        category_stats[category] = category_stats.get(category, 0) + 1
    
    if not preview and changes:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        for change in changes:
            try:
                target_dir = Path(change['new_path']).parent
                target_dir.mkdir(parents=True, exist_ok=True)
                
                if copy:
                    shutil.copy2(change['old_path'], change['new_path'])
                else:
                    shutil.move(change['old_path'], change['new_path'])
                change['success'] = True
            except Exception as e:
                change['success'] = False
                change['error'] = str(e)
        
        save_operation(
            operation_type='classify',
            changes=changes,
            description=f"分类整理 {len(changes)} 个文件到 {output_dir}"
        )
    
    return {
        'files': files,
        'changes': changes,
        'categories': category_stats,
        'total': len(files),
        'classified': len(changes)
    }


def print_classify_result(result: Dict, preview: bool = False):
    action = "预览" if preview else "分类"
    
    click.echo("=" * 70)
    click.echo(f"{action}结果: 共扫描 {result['total']} 个文件")
    click.echo(f"将{action} {result['classified']} 个文件到 {len(result['categories'])} 个分类")
    click.echo("=" * 70)
    
    click.echo("")
    click.echo("分类统计:")
    for category, count in sorted(result['categories'].items()):
        click.echo(f"  {category}: {count} 个文件")
    
    if result['changes']:
        click.echo("")
        click.echo("分类详情:")
        click.echo("-" * 70)
        current_category = None
        for change in result['changes']:
            if change['category'] != current_category:
                current_category = change['category']
                click.echo(f"\n[{current_category}]")
            
            click.echo(f"  {change['old_name']}")
            if 'success' in change and not change['success']:
                click.echo(f"    错误: {change.get('error', '未知错误')}", err=True)
        
        click.echo("")
    
    if preview:
        click.echo("这是预览模式，未执行实际操作。")
        click.echo("去掉 --preview 参数执行实际分类。")
