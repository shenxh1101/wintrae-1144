import os
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Generator

SUPPORTED_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.csv', '.jpg', '.jpeg', '.png', '.gif', '.bmp',
    '.zip', '.rar', '.7z', '.eml', '.msg'
}


def get_file_hash(filepath: str, chunk_size: int = 8192) -> str:
    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        while chunk := f.read(chunk_size):
            md5.update(chunk)
    return md5.hexdigest()


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def parse_size(size_str: str) -> int:
    size_str = size_str.strip().upper()
    match = re.match(r'^(\d+(?:\.\d+)?)\s*(B|KB|MB|GB)?$', size_str)
    if not match:
        raise ValueError(f"无效的大小格式: {size_str}")
    
    value = float(match.group(1))
    unit = match.group(2) or 'B'
    
    multipliers = {'B': 1, 'KB': 1024, 'MB': 1024 * 1024, 'GB': 1024 * 1024 * 1024}
    return int(value * multipliers[unit])


def scan_directory(
    directory: str,
    recursive: bool = True,
    extensions: Optional[List[str]] = None,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    date_type: str = 'modified'
) -> List[Dict]:
    directory = Path(directory).resolve()
    if not directory.exists():
        raise FileNotFoundError(f"目录不存在: {directory}")
    
    files = []
    iterator = directory.rglob('*') if recursive else directory.glob('*')
    
    for path in iterator:
        if not path.is_file():
            continue
        
        if extensions:
            ext_list = [e.lower() if e.startswith('.') else f'.{e.lower()}' for e in extensions]
            if path.suffix.lower() not in ext_list:
                continue
        
        stat = path.stat()
        size = stat.st_size
        
        if min_size and size < min_size:
            continue
        if max_size and size > max_size:
            continue
        
        mtime = datetime.fromtimestamp(stat.st_mtime)
        ctime = datetime.fromtimestamp(stat.st_ctime)
        file_time = mtime if date_type == 'modified' else ctime
        
        if date_from and file_time < date_from:
            continue
        if date_to and file_time > date_to:
            continue
        
        files.append({
            'path': str(path),
            'name': path.name,
            'stem': path.stem,
            'suffix': path.suffix,
            'size': size,
            'size_formatted': format_size(size),
            'modified': mtime,
            'created': ctime,
            'extension': path.suffix.lower(),
            'parent': str(path.parent)
        })
    
    return sorted(files, key=lambda x: x['name'])


def find_duplicates(files: List[Dict]) -> Dict[str, List[Dict]]:
    hash_map: Dict[str, List[Dict]] = {}
    for f in files:
        try:
            file_hash = get_file_hash(f['path'])
            f['hash'] = file_hash
            if file_hash not in hash_map:
                hash_map[file_hash] = []
            hash_map[file_hash].append(f)
        except (IOError, OSError):
            continue
    
    return {h: group for h, group in hash_map.items() if len(group) > 1}


def extract_date_from_name(filename: str) -> Optional[datetime]:
    patterns = [
        r'(\d{4})[-_](\d{1,2})[-_](\d{1,2})',
        r'(\d{4})(\d{2})(\d{2})',
        r'(\d{1,2})[-_](\d{1,2})[-_](\d{4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                groups = match.groups()
                if len(groups[0]) == 4:
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                else:
                    day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                return datetime(year, month, day)
            except (ValueError, IndexError):
                continue
    return None


def extract_number_from_name(filename: str) -> Optional[str]:
    patterns = [
        r'(?:NO|No|no|编号|№)[\s:：_-]*([A-Za-z0-9_-]+)',
        r'(\d{6,})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return match.group(1)
    return None


def safe_filename(name: str) -> str:
    invalid_chars = r'[\\/:*?"<>|]'
    return re.sub(invalid_chars, '_', name).strip()


def parse_date(date_str: str) -> datetime:
    formats = [
        '%Y-%m-%d', '%Y/%m/%d', '%Y%m%d',
        '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {date_str}")


def match_keywords(text: str, keywords: List[str]) -> List[str]:
    text_lower = text.lower()
    matched = []
    for kw in keywords:
        if kw.lower() in text_lower:
            matched.append(kw)
    return matched
