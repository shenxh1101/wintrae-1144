import os
import click
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from ..utils import (
    scan_directory, find_duplicates, parse_size, parse_date,
    format_size
)
from ..history import generate_report


def scan_command(
    directory: str,
    recursive: bool = True,
    extensions: Optional[List[str]] = None,
    min_size: Optional[str] = None,
    max_size: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    date_type: str = 'modified',
    find_dup: bool = False,
    show_details: bool = False
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
    
    duplicates = {}
    if find_dup and files:
        duplicates = find_duplicates(files)
    
    result = {
        'files': files,
        'duplicates': duplicates,
        'total': len(files),
        'total_size': sum(f['size'] for f in files),
        'duplicate_groups': len(duplicates),
        'duplicate_files': sum(len(g) for g in duplicates.values())
    }
    
    return result


def print_scan_result(result: Dict, show_details: bool = False):
    click.echo("=" * 70)
    click.echo(f"扫描结果: 共找到 {result['total']} 个文件")
    click.echo(f"总大小: {format_size(result['total_size'])}")
    
    if result['duplicate_groups'] > 0:
        click.echo(f"发现 {result['duplicate_groups']} 组重复文件，共 {result['duplicate_files']} 个")
    click.echo("=" * 70)
    
    if show_details:
        click.echo("")
        click.echo(f"{'文件名':<40} {'大小':>12} {'修改时间':<20}")
        click.echo("-" * 72)
        for f in result['files']:
            name = f['name']
            if len(name) > 38:
                name = name[:35] + "..."
            mtime = f['modified'].strftime('%Y-%m-%d %H:%M')
            click.echo(f"{name:<40} {f['size_formatted']:>12} {mtime:<20}")
        click.echo("")
    
    if result['duplicates']:
        click.echo("")
        click.echo("重复文件列表:")
        click.echo("-" * 70)
        for i, (file_hash, group) in enumerate(result['duplicates'].items(), 1):
            click.echo(f"\n重复组 #{i} (MD5: {file_hash[:16]}...)")
            for f in group:
                click.echo(f"  → {f['path']}")
