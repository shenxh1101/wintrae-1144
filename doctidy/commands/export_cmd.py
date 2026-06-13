import os
import click
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from ..utils import scan_directory, parse_size, parse_date, format_size
from ..exporter import (
    export_to_csv, export_to_json, export_to_excel, 
    export_markdown_report, detect_export_format
)
from ..history import generate_report


def export_command(
    directory: str,
    output_file: str,
    recursive: bool = True,
    extensions: Optional[List[str]] = None,
    format: Optional[str] = None,
    include_details: bool = True,
    include_report: bool = False,
    min_size: Optional[str] = None,
    max_size: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    date_type: str = 'modified'
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
    
    if not format:
        format = detect_export_format(output_file)
    
    format = format.lower()
    
    report_files = files if include_details else []
    
    if format == 'csv':
        export_to_csv(report_files, output_file)
    elif format == 'json':
        data = generate_report(
            operation='export',
            files=report_files,
            changes=[],
            total_files=len(files)
        )
        export_to_json(data, output_file)
    elif format == 'excel':
        export_to_excel(report_files, output_file)
    elif format == 'markdown':
        report = generate_report(
            operation='export',
            files=report_files,
            changes=[],
            total_files=len(files)
        )
        export_markdown_report(report, output_file)
    else:
        raise ValueError(f"不支持的导出格式: {format}")
    
    return {
        'files': files,
        'output_file': output_file,
        'format': format,
        'total': len(files),
        'total_size': sum(f['size'] for f in files)
    }


def print_export_result(result: Dict):
    click.echo("=" * 70)
    click.echo(f"导出完成: 共导出 {result['total']} 个文件")
    click.echo(f"总大小: {format_size(result['total_size'])}")
    click.echo(f"格式: {result['format'].upper()}")
    click.echo(f"输出文件: {result['output_file']}")
    click.echo("=" * 70)
    
    if result['files']:
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
