import os
from typing import List, Optional
from pathlib import Path

try:
    from PyPDF2 import PdfReader, PdfWriter
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


def is_pdf_available() -> bool:
    return PYPDF_AVAILABLE


def get_pdf_page_count(filepath: str) -> Optional[int]:
    if not PYPDF_AVAILABLE:
        return None
    try:
        reader = PdfReader(filepath)
        return len(reader.pages)
    except Exception:
        return None


def merge_pdfs(input_files: List[str], output_file: str, overwrite: bool = False) -> bool:
    if not PYPDF_AVAILABLE:
        raise ImportError("需要安装 PyPDF2 才能使用 PDF 合并功能")
    
    output_path = Path(output_file)
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"输出文件已存在: {output_file}")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    writer = PdfWriter()
    files_merged = 0
    
    try:
        for input_file in input_files:
            if not os.path.exists(input_file):
                continue
            if Path(input_file).suffix.lower() != '.pdf':
                continue
            
            try:
                reader = PdfReader(input_file)
                for page in reader.pages:
                    writer.add_page(page)
                files_merged += 1
            except Exception as e:
                print(f"警告: 无法读取 {input_file}: {e}")
                continue
        
        if files_merged == 0:
            return False
        
        with open(output_file, 'wb') as f:
            writer.write(f)
        
        return True
    
    finally:
        writer.close()
