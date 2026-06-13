import os
import click
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from ..utils import (
    scan_directory, extract_date_from_name, match_keywords,
    parse_size, parse_date, safe_filename
)
from ..pdf_utils import merge_pdfs, is_pdf_available, get_pdf_page_count
from ..history import save_operation


def group_pdfs(files: List[Dict], group_by: str, 
               keywords: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
    groups: Dict[str, List[Dict]] = {}
    
    for f in files:
        if f['extension'] != '.pdf':
            continue
        
        group_key = ''
        
        if group_by == 'keyword':
            if keywords:
                matched = match_keywords(f['name'], keywords)
                if matched:
                    group_key = '_'.join(matched)
                else:
                    group_key = '其他'
            else:
                group_key = '合并'
        
        elif group_by == 'date':
            date_obj = extract_date_from_name(f['name']) or f['modified']
            group_key = date_obj.strftime('%Y%m')
        
        elif group_by == 'prefix':
            name = f['stem']
            if '_' in name:
                group_key = name.split('_')[0]
            elif '-' in name:
                group_key = name.split('-')[0]
            else:
                group_key = name[:4] if len(name) >= 4 else name
        
        elif group_by == 'parent':
            group_key = Path(f['parent']).name or '根目录'
        
        group_key = safe_filename(group_key)
        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(f)
    
    return groups


def sort_files(files: List[Dict], sort_by: str) -> List[Dict]:
    if sort_by == 'name':
        return sorted(files, key=lambda x: x['name'])
    elif sort_by == 'date':
        return sorted(files, key=lambda x: x['modified'])
    elif sort_by == 'size':
        return sorted(files, key=lambda x: x['size'])
    elif sort_by == 'date_name':
        return sorted(files, key=lambda x: (
            extract_date_from_name(x['name']) or x['modified'],
            x['name']
        ))
    return files


def merge_command(
    directory: str,
    output_dir: str,
    recursive: bool = False,
    group_by: str = 'keyword',
    keywords: Optional[List[str]] = None,
    sort_by: str = 'name',
    output_pattern: str = '{group}_合并.pdf',
    overwrite: bool = False,
    preview: bool = False,
    min_size: Optional[str] = None,
    max_size: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> Dict:
    if not is_pdf_available():
        raise ImportError("需要安装 PyPDF2 才能使用 PDF 合并功能，请运行: pip install PyPDF2")
    
    min_size_bytes = parse_size(min_size) if min_size else None
    max_size_bytes = parse_size(max_size) if max_size else None
    date_from_dt = parse_date(date_from) if date_from else None
    date_to_dt = parse_date(date_to) if date_to else None
    
    files = scan_directory(
        directory=directory,
        recursive=recursive,
        extensions=['pdf'],
        min_size=min_size_bytes,
        max_size=max_size_bytes,
        date_from=date_from_dt,
        date_to=date_to_dt
    )
    
    pdf_files = [f for f in files if f['extension'] == '.pdf']
    
    groups = group_pdfs(pdf_files, group_by, keywords)
    
    changes = []
    group_stats: Dict[str, Dict] = {}
    
    for group_name, group_files in groups.items():
        if len(group_files) < 2:
            continue
        
        sorted_files = sort_files(group_files, sort_by)
        
        output_name = output_pattern.replace('{group}', safe_filename(group_name))
        output_name = output_name.replace('{date}', datetime.now().strftime('%Y%m%d'))
        output_path = str(Path(output_dir) / safe_filename(output_name))
        
        total_pages = 0
        for f in sorted_files:
            pages = get_pdf_page_count(f['path'])
            if pages:
                total_pages += pages
        
        changes.append({
            'group': group_name,
            'files': [f['path'] for f in sorted_files],
            'file_count': len(sorted_files),
            'total_pages': total_pages,
            'merged_file': output_path
        })
        
        group_stats[group_name] = {
            'count': len(sorted_files),
            'total_pages': total_pages,
            'total_size': sum(f['size'] for f in sorted_files)
        }
    
    if not preview and changes:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        for change in changes:
            try:
                success = merge_pdfs(
                    input_files=change['files'],
                    output_file=change['merged_file'],
                    overwrite=overwrite
                )
                change['success'] = success
            except Exception as e:
                change['success'] = False
                change['error'] = str(e)
        
        save_operation(
            operation_type='merge',
            changes=changes,
            description=f"合并 PDF 为 {len(changes)} 个文件"
        )
    
    return {
        'files': pdf_files,
        'changes': changes,
        'groups': group_stats,
        'total_pdfs': len(pdf_files),
        'merged_count': len(changes)
    }


def print_merge_result(result: Dict, preview: bool = False):
    action = "预览" if preview else "合并"
    
    click.echo("=" * 70)
    click.echo(f"{action}结果: 共找到 {result['total_pdfs']} 个 PDF 文件")
    click.echo(f"将{action}为 {result['merged_count']} 个合并文件")
    click.echo("=" * 70)
    
    if result['groups']:
        click.echo("")
        click.echo("分组统计:")
        for group_name, stats in sorted(result['groups'].items()):
            click.echo(f"  {group_name}: {stats['count']} 个文件, {stats['total_pages']} 页")
    
    if result['changes']:
        click.echo("")
        click.echo("合并详情:")
        click.echo("-" * 70)
        for i, change in enumerate(result['changes'], 1):
            click.echo(f"\n{i}. 分组: {change['group']}")
            click.echo(f"   输出: {change['merged_file']}")
            click.echo(f"   包含 {change['file_count']} 个文件:")
            for j, f in enumerate(change['files'], 1):
                click.echo(f"     {j}. {os.path.basename(f)}")
            
            if 'success' in change:
                if change['success']:
                    click.echo(f"   状态: 成功")
                else:
                    click.echo(f"   状态: 失败 - {change.get('error', '未知错误')}", err=True)
        
        click.echo("")
    
    if preview:
        click.echo("这是预览模式，未执行实际合并。")
        click.echo("去掉 --preview 参数执行实际合并。")
