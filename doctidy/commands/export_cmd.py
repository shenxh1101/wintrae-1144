import os
import click
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from ..utils import scan_directory, parse_size, parse_date, format_size, find_duplicates
from ..exporter import (
    export_file_list_csv, export_file_list_excel,
    export_file_list_json, export_file_list_markdown,
    export_report_json, export_report_markdown,
    detect_export_format
)
from ..history import generate_report
from ..config import load_config, get_scan_extensions


def export_command(
    directory: str,
    output_file: str,
    recursive: bool = True,
    extensions: Optional[List[str]] = None,
    format: Optional[str] = None,
    report_mode: bool = False,
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
    
    if not format:
        format = detect_export_format(output_file)
    fmt = format.lower()
    
    if report_mode:
        _export_report(files, fmt, output_file)
    else:
        _export_file_list(files, fmt, output_file)
    
    return {
        'files': files,
        'output_file': output_file,
        'format': fmt,
        'report_mode': report_mode,
        'total': len(files),
        'total_size': sum(f['size'] for f in files)
    }


def _export_file_list(files: List[Dict], fmt: str, output_file: str):
    if fmt == 'csv':
        export_file_list_csv(files, output_file)
    elif fmt == 'excel':
        export_file_list_excel(files, output_file)
    elif fmt == 'json':
        export_file_list_json(files, output_file)
    elif fmt == 'markdown':
        export_file_list_markdown(files, output_file)
    else:
        export_file_list_csv(files, output_file)


def _export_report(files: List[Dict], fmt: str, output_file: str):
    duplicates = find_duplicates(files) if files else {}
    report = generate_report(
        operation='export',
        files=files,
        changes=[],
        duplicates=duplicates if duplicates else None,
        total_files=len(files)
    )
    if fmt == 'json':
        export_report_json(report, output_file)
    elif fmt == 'markdown':
        export_report_markdown(report, output_file)
    elif fmt == 'csv':
        export_report_json(report, output_file)
        click.echo(f"提示: CSV 格式不支持报告模式，已改用 JSON 输出", err=True)
    elif fmt == 'excel':
        export_report_json(report, output_file)
        click.echo(f"提示: Excel 格式不支持报告模式，已改用 JSON 输出", err=True)
    else:
        export_report_json(report, output_file)


def print_export_result(result: Dict):
    mode_label = "整理报告" if result['report_mode'] else "文件清单"
    click.echo("=" * 70)
    click.echo(f"导出完成（{mode_label}）: 共 {result['total']} 个文件")
    click.echo(f"总大小: {format_size(result['total_size'])}")
    click.echo(f"格式: {result['format'].upper()}")
    click.echo(f"输出文件: {result['output_file']}")
    click.echo("=" * 70)
    
    if result['files'] and not result['report_mode']:
        click.echo("")
        click.echo(f"{'序号':<6} {'文件名':<40} {'大小':>12} {'修改时间':<20}")
        click.echo("-" * 78)
        for i, f in enumerate(result['files'][:50], 1):
            name = f['name']
            if len(name) > 38:
                name = name[:35] + "..."
            mtime = f['modified'].strftime('%Y-%m-%d %H:%M')
            click.echo(f"{i:<6} {name:<40} {f['size_formatted']:>12} {mtime:<20}")
        
        if len(result['files']) > 50:
            click.echo(f"... 还有 {len(result['files']) - 50} 个文件未显示")
