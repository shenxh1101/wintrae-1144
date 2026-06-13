import os
import re
import click
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from pathlib import Path

from ..utils import (
    scan_directory, find_duplicates, get_file_hash, parse_size,
    parse_date, format_size, match_keywords
)
from ..history import generate_report
from ..config import load_config, get_main_doc_patterns, get_attachment_patterns


def _build_main_doc_patterns(config_path: Optional[str] = None) -> List[str]:
    config = load_config(config_path) if config_path else None
    return get_main_doc_patterns(config)


def _build_attachment_patterns(config_path: Optional[str] = None) -> List[Tuple[str, str]]:
    config = load_config(config_path) if config_path else None
    raw = get_attachment_patterns(config)
    result = []
    for item in raw:
        result.append((item['regex'], item['template']))
    return result

NUMBER_PATTERNS = [
    r'[（(](\d+)[)）]',
    r'[-_](\d+)[-_]',
    r'第(\d+)号',
    r'NO[.\s_-]*(\d+)',
    r'编号[.\s_-]*(\d+)',
]


def extract_doc_number(filename: str) -> Optional[str]:
    for pattern in NUMBER_PATTERNS:
        match = re.search(pattern, filename)
        if match:
            return match.group(1)
    return None


def is_main_document(filename: str, config_path: Optional[str] = None) -> bool:
    patterns = _build_main_doc_patterns(config_path)
    for pattern in patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            return True
    return False


def find_expected_attachments(filename: str, files: List[Dict], 
                               config_path: Optional[str] = None) -> List[str]:
    if not is_main_document(filename, config_path):
        return []
    
    attachment_patterns = _build_attachment_patterns(config_path)
    doc_num = extract_doc_number(filename)
    expected = []
    
    file_names = {f['name'] for f in files}
    file_stems = {f['stem'] for f in files}
    
    for pattern, template in attachment_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match and match.group(1):
            start_num = int(match.group(1))
            for n in range(1, start_num + 5):
                att_name = template.format(num=n if n > 1 else '')
                if doc_num:
                    candidates = [
                        f"{doc_num}_{att_name}",
                        f"{att_name}_{doc_num}",
                        att_name,
                    ]
                else:
                    candidates = [att_name]
                
                for cand in candidates:
                    found = False
                    for existing_name in file_stems:
                        if cand.lower() in existing_name.lower():
                            found = True
                            break
                    if not found and cand not in expected:
                        expected.append(cand)
    
    text = Path(filename).read_text(errors='ignore') if Path(filename).suffix.lower() in ['.txt', '.md'] else ''
    for pattern, template in attachment_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            num_str = m if isinstance(m, str) else (m[0] if m else '')
            n = int(num_str) if num_str.isdigit() else 1
            att_name = template.format(num=n if n > 1 else '')
            found = any(att_name.lower() in fn.lower() for fn in file_stems)
            if not found and att_name not in expected:
                expected.append(att_name)
    
    return expected


def check_attachments(files: List[Dict], config_path: Optional[str] = None) -> Dict[str, List[str]]:
    missing_map: Dict[str, List[str]] = {}
    
    main_docs = [f for f in files if is_main_document(f['name'], config_path)]
    
    for doc in main_docs:
        missing = find_expected_attachments(doc['path'], files, config_path)
        if missing:
            missing_map[doc['path']] = missing
    
    return missing_map


def check_command(
    directory: str,
    recursive: bool = True,
    extensions: Optional[List[str]] = None,
    check_duplicates: bool = True,
    check_missing: bool = True,
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
    
    duplicates = {}
    if check_duplicates and files:
        duplicates = find_duplicates(files)
    
    missing_attachments = {}
    if check_missing and files:
        missing_attachments = check_attachments(files, config_path)
    
    all_missing = []
    for doc, missing in missing_attachments.items():
        for m in missing:
            all_missing.append(f"{os.path.basename(doc)} 缺少 {m}")
    
    return {
        'files': files,
        'duplicates': duplicates,
        'missing_attachments': missing_attachments,
        'all_missing': all_missing,
        'total': len(files),
        'duplicate_groups': len(duplicates),
        'duplicate_files': sum(len(g) for g in duplicates.values()),
        'docs_with_missing': len(missing_attachments),
        'total_missing': len(all_missing)
    }


def print_check_result(result: Dict):
    click.echo("=" * 70)
    click.echo(f"检查结果: 共扫描 {result['total']} 个文件")
    click.echo(f"重复文件: {result['duplicate_groups']} 组, 共 {result['duplicate_files']} 个")
    click.echo(f"缺失附件: {result['total_missing']} 个 (涉及 {result['docs_with_missing']} 个文档)")
    click.echo("=" * 70)
    
    if result['duplicates']:
        click.echo("")
        click.echo("重复文件列表:")
        click.echo("-" * 70)
        for i, (file_hash, group) in enumerate(result['duplicates'].items(), 1):
            click.echo(f"\n重复组 #{i} (MD5: {file_hash[:16]}...)")
            for f in group:
                click.echo(f"  → {f['path']} ({f['size_formatted']})")
    
    if result['missing_attachments']:
        click.echo("")
        click.echo("缺失附件列表:")
        click.echo("-" * 70)
        for doc_path, missing in result['missing_attachments'].items():
            click.echo(f"\n文档: {os.path.basename(doc_path)}")
            click.echo(f"  路径: {doc_path}")
            click.echo(f"  缺少附件:")
            for m in missing:
                click.echo(f"    - {m}")
    
    if not result['duplicates'] and not result['missing_attachments']:
        click.echo("")
        click.echo("✓ 检查通过，未发现问题！")
