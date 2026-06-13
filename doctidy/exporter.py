import os
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def export_to_csv(files: List[Dict], output_file: str):
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not files:
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            pass
        return
    
    fieldnames = list(files[0].keys())
    
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in files:
            row_copy = {}
            for k, v in row.items():
                if isinstance(v, datetime):
                    row_copy[k] = v.isoformat()
                else:
                    row_copy[k] = v
            writer.writerow(row_copy)


def export_to_json(data: Dict, output_file: str):
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return super().default(obj)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)


def export_to_excel(files: List[Dict], output_file: str, sheet_name: str = "文件清单"):
    if not PANDAS_AVAILABLE:
        raise ImportError("需要安装 pandas 和 openpyxl 才能导出 Excel")
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df = pd.DataFrame(files)
    
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        worksheet = writer.sheets[sheet_name]
        for idx, col in enumerate(df.columns):
            max_len = max(
                df[col].astype(str).map(len).max(),
                len(str(col))
            ) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_len, 50)


def export_markdown_report(report: Dict, output_file: str):
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    lines = []
    
    lines.append(f"# 文档整理报告 - {report['operation']}")
    lines.append("")
    lines.append(f"**生成时间**: {report['timestamp']}")
    lines.append("")
    
    lines.append("## 汇总统计")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    for k, v in report['summary'].items():
        label_k = {
            'total_files': '文件总数',
            'total_changes': '变动数量',
            'duplicate_groups': '重复组数量',
            'duplicate_files': '重复文件数',
            'missing_count': '缺失附件数'
        }.get(k, k)
        lines.append(f"| {label_k} | {v} |")
    lines.append("")
    
    if 'duplicates' in report and report['duplicates']['groups']:
        lines.append("## 重复文件")
        lines.append("")
        for i, group in enumerate(report['duplicates']['groups'], 1):
            lines.append(f"### 重复组 {i} (共 {len(group)} 个文件)")
            lines.append("")
            for f in group:
                lines.append(f"- `{f['path']}` ({f['size_formatted']})")
            lines.append("")
    
    if 'missing_attachments' in report and report['missing_attachments']:
        lines.append("## 缺失附件")
        lines.append("")
        for item in report['missing_attachments']:
            lines.append(f"- {item}")
        lines.append("")
    
    if report['changes']:
        lines.append("## 操作变动")
        lines.append("")
        for i, change in enumerate(report['changes'], 1):
            lines.append(f"{i}. `{change.get('old_path', change.get('path', ''))}`")
            if 'new_path' in change:
                lines.append(f"   → `{change['new_path']}`")
            if 'action' in change:
                lines.append(f"   操作: {change['action']}")
            lines.append("")
    
    if report.get('files'):
        lines.append("## 文件清单")
        lines.append("")
        lines.append("| 文件名 | 大小 | 修改时间 | 路径 |")
        lines.append("|--------|------|----------|------|")
        for f in report['files']:
            mtime = f['modified'] if isinstance(f['modified'], str) else f['modified'].strftime('%Y-%m-%d %H:%M:%S')
            lines.append(f"| {f['name']} | {f['size_formatted']} | {mtime} | `{f['path']}` |")
        lines.append("")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def detect_export_format(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    if ext == '.csv':
        return 'csv'
    elif ext in ('.xlsx', '.xls'):
        return 'excel'
    elif ext == '.json':
        return 'json'
    elif ext in ('.md', '.markdown'):
        return 'markdown'
    else:
        return 'csv'
