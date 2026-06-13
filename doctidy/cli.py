import os
import sys
import click
from datetime import datetime
from typing import List, Optional

from . import __version__
from .commands.scan_cmd import scan_command, print_scan_result
from .commands.rename_cmd import rename_command, print_rename_result
from .commands.classify_cmd import classify_command, print_classify_result
from .commands.merge_cmd import merge_command, print_merge_result
from .commands.check_cmd import check_command, print_check_result
from .commands.export_cmd import export_command, print_export_result
from .history import get_history, undo_operation


common_options = [
    click.option('--recursive/--no-recursive', default=True, help='是否递归扫描子目录'),
    click.option('--extension', '-e', 'extensions', multiple=True, help='按扩展名筛选，可多次指定'),
    click.option('--min-size', help='最小文件大小，如 1MB、500KB'),
    click.option('--max-size', help='最大文件大小，如 100MB'),
    click.option('--date-from', help='起始日期，格式 YYYY-MM-DD'),
    click.option('--date-to', help='结束日期，格式 YYYY-MM-DD'),
    click.option('--date-type', type=click.Choice(['modified', 'created']), default='modified',
                 help='日期筛选使用修改时间还是创建时间'),
]


def add_common_options(func):
    for option in reversed(common_options):
        func = option(func)
    return func


@click.group(invoke_without_command=True)
@click.version_option(__version__, '-v', '--version')
@click.option('--help', '-h', is_flag=True, help='显示帮助信息')
def main(help):
    """文档批量整理工具 - 扫描、重命名、分类、合并、检查、导出
    
    常用命令：
    
      scan     扫描目录，查看文件清单，识别重复文件
    
      rename   按日期、编号、关键词批量重命名
    
      classify 按规则将文件移动到分类文件夹
    
      merge    合并同类 PDF 文件
    
      check    检查重复文件和缺失附件
    
      export   导出文件目录清单和整理报告
    
      undo     撤销上次操作
    
      history  查看操作历史
    
    示例：
    
      doctidy scan ./docs --duplicates
    
      doctidy rename ./docs --pattern "{date}_{name}" --preview
    
      doctidy classify ./docs -o ./sorted --method keyword
    
      doctidy merge ./pdfs -o ./merged --group-by keyword --keyword 合同,报告
    
      doctidy check ./docs
    
      doctidy export ./docs -o 目录清单.xlsx
    """
    if help:
        click.echo(main.help)
        return
    pass


@main.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
@add_common_options
@click.option('--duplicates', '-d', 'find_dup', is_flag=True, help='查找重复文件（基于MD5）')
@click.option('--details', '-D', is_flag=True, help='显示详细文件列表')
def scan(directory, recursive, extensions, min_size, max_size, 
         date_from, date_to, date_type, find_dup, details):
    """扫描目录，查看文件清单，识别重复文件
    
    DIRECTORY: 要扫描的目录路径
    
    示例：
    
      doctidy scan ./docs
    
      doctidy scan ./docs --duplicates --details
    
      doctidy scan ./docs -e pdf -e docx --min-size 1MB
    """
    try:
        ext_list = list(extensions) if extensions else None
        result = scan_command(
            directory=directory,
            recursive=recursive,
            extensions=ext_list,
            min_size=min_size,
            max_size=max_size,
            date_from=date_from,
            date_to=date_to,
            date_type=date_type,
            find_dup=find_dup,
            show_details=details
        )
        print_scan_result(result, details)
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
@click.option('--pattern', '-p', required=True,
              help='命名模式，支持变量: {date}, {date-}, {date_}, {year}, {month}, {day}, {number}, {name}, {keyword}, {counter}')
@add_common_options
@click.option('--date-source', type=click.Choice(['auto', 'modified', 'created', 'custom']), default='auto',
              help='日期来源: auto(文件名优先), modified, created, custom')
@click.option('--custom-date', help='自定义日期，格式 YYYY-MM-DD，配合 --date-source custom 使用')
@click.option('--keyword', '-k', 'keywords', multiple=True, help='关键词，可多次指定')
@click.option('--output-dir', '-o', type=click.Path(file_okay=False), help='输出目录，默认原地重命名')
@click.option('--preview', '-P', is_flag=True, help='预览模式，不实际执行')
def rename(directory, pattern, recursive, extensions, min_size, max_size,
           date_from, date_to, date_type, date_source, custom_date, 
           keywords, output_dir, preview):
    """按日期、编号、关键词批量重命名
    
    DIRECTORY: 要处理的目录路径
    
    命名模式变量：
    
      {date}      日期，格式 20240115
    
      {date-}     日期，格式 2024-01-15
    
      {date_}     日期，格式 2024_01_15
    
      {year}      年，如 2024
    
      {month}     月，如 01
    
      {day}       日，如 15
    
      {number}    从文件名提取的编号
    
      {name}      原文件名（不含扩展名）
    
      {keyword}   匹配的关键词
    
      {counter}   三位序号，如 001
    
      {counter2}  两位序号，如 01
    
    示例：
    
      doctidy rename ./docs --pattern "{date}_{name}"
    
      doctidy rename ./docs -p "{year}-{month}/{name}" --date-source modified
    
      doctidy rename ./docs -p "合同_{date}_{counter}" -k 合同 --preview
    """
    try:
        if date_source == 'custom' and not custom_date:
            raise click.UsageError('使用 --date-source custom 时必须提供 --custom-date')
        
        ext_list = list(extensions) if extensions else None
        kw_list = list(keywords) if keywords else None
        
        result = rename_command(
            directory=directory,
            pattern=pattern,
            recursive=recursive,
            extensions=ext_list,
            date_source=date_source,
            custom_date=custom_date,
            keywords=kw_list,
            output_dir=output_dir,
            preview=preview,
            min_size=min_size,
            max_size=max_size,
            date_from=date_from,
            date_to=date_to,
            date_type=date_type
        )
        print_rename_result(result, preview)
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
@click.option('--output-dir', '-o', required=True, type=click.Path(file_okay=False),
              help='分类输出目录')
@add_common_options
@click.option('--method', '-m', type=click.Choice(['keyword', 'extension', 'date', 'all']), 
              default='keyword', help='分类方式')
@click.option('--rules-file', '-r', type=click.Path(exists=True, dir_okay=False),
              help='分类规则文件（JSON格式）')
@click.option('--rule', '-R', 'rules', multiple=True,
              help='自定义分类规则，格式: 分类名:关键词1,关键词2')
@click.option('--date-format', default='%Y-%m', help='按日期分类时的格式，默认 %Y-%m')
@click.option('--copy/--move', default=False, help='复制而不是移动文件')
@click.option('--preview', '-P', is_flag=True, help='预览模式，不实际执行')
def classify(directory, output_dir, recursive, extensions, min_size, max_size,
             date_from, date_to, date_type, method, rules_file, rules, 
             date_format, copy, preview):
    """按规则将文件移动到分类文件夹
    
    DIRECTORY: 要处理的目录路径
    
    分类方式：
    
      keyword    按关键词匹配（默认规则：合同、报告、发票、证件等）
    
      extension  按文件扩展名分类（文档、表格、图片、压缩包等）
    
      date       按日期分类
    
      all        依次使用关键词、扩展名分类
    
    示例：
    
      doctidy classify ./docs -o ./sorted
    
      doctidy classify ./docs -o ./sorted --method extension
    
      doctidy classify ./docs -o ./sorted -R "合同:合同,协议" -R "报告:报告,分析" --preview
    
      doctidy classify ./docs -o ./sorted --method date --date-format %Y
    """
    try:
        ext_list = list(extensions) if extensions else None
        rule_list = list(rules) if rules else None
        
        result = classify_command(
            directory=directory,
            output_dir=output_dir,
            recursive=recursive,
            extensions=ext_list,
            method=method,
            rules_file=rules_file,
            rules=rule_list,
            date_format=date_format,
            copy=copy,
            preview=preview,
            min_size=min_size,
            max_size=max_size,
            date_from=date_from,
            date_to=date_to,
            date_type=date_type
        )
        print_classify_result(result, preview)
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
@click.option('--output-dir', '-o', required=True, type=click.Path(file_okay=False),
              help='合并输出目录')
@add_common_options
@click.option('--group-by', type=click.Choice(['keyword', 'date', 'prefix', 'parent']),
              default='keyword', help='PDF分组方式')
@click.option('--keyword', '-k', 'keywords', multiple=True, help='分组关键词，可多次指定')
@click.option('--sort-by', type=click.Choice(['name', 'date', 'size', 'date_name']),
              default='name', help='合并时的排序方式')
@click.option('--output-pattern', default='{group}_合并.pdf',
              help='输出文件名模式，支持 {group} 和 {date}')
@click.option('--overwrite', is_flag=True, help='覆盖已存在的输出文件')
@click.option('--preview', '-P', is_flag=True, help='预览模式，不实际执行')
def merge(directory, output_dir, recursive, extensions, min_size, max_size,
          date_from, date_to, date_type, group_by, keywords, sort_by,
          output_pattern, overwrite, preview):
    """合并同类 PDF 文件
    
    DIRECTORY: 要处理的目录路径
    
    分组方式：
    
      keyword   按关键词分组（默认）
    
      date      按文件日期（年月）分组
    
      prefix    按文件名前缀（下划线或横杠前的部分）分组
    
      parent    按所在父目录分组
    
    示例：
    
      doctidy merge ./pdfs -o ./merged --group-by keyword -k 合同 -k 报告
    
      doctidy merge ./pdfs -o ./merged --group-by date --sort-by date_name
    
      doctidy merge ./pdfs -o ./merged --group-by parent --preview
    """
    try:
        ext_list = list(extensions) if extensions else None
        kw_list = list(keywords) if keywords else None
        
        result = merge_command(
            directory=directory,
            output_dir=output_dir,
            recursive=recursive,
            extensions=ext_list,
            group_by=group_by,
            keywords=kw_list,
            sort_by=sort_by,
            output_pattern=output_pattern,
            overwrite=overwrite,
            preview=preview,
            min_size=min_size,
            max_size=max_size,
            date_from=date_from,
            date_to=date_to,
            date_type=date_type
        )
        print_merge_result(result, preview)
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
@add_common_options
@click.option('--no-duplicates', 'no_dup', is_flag=True, help='不检查重复文件')
@click.option('--no-missing', 'no_miss', is_flag=True, help='不检查缺失附件')
def check(directory, recursive, extensions, min_size, max_size,
          date_from, date_to, date_type, no_dup, no_miss):
    """检查重复文件和缺失附件
    
    DIRECTORY: 要检查的目录路径
    
    检查项：
    
      1. 重复文件（基于 MD5 哈希值）
    
      2. 缺失附件（根据主文档内容查找引用的附件）
    
    示例：
    
      doctidy check ./docs
    
      doctidy check ./docs --no-missing
    
      doctidy check ./docs -e pdf --min-size 100KB
    """
    try:
        ext_list = list(extensions) if extensions else None
        
        result = check_command(
            directory=directory,
            recursive=recursive,
            extensions=ext_list,
            check_duplicates=not no_dup,
            check_missing=not no_miss,
            min_size=min_size,
            max_size=max_size,
            date_from=date_from,
            date_to=date_to,
            date_type=date_type
        )
        print_check_result(result)
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
@click.option('--output', '-o', 'output_file', required=True,
              type=click.Path(dir_okay=False), help='输出文件路径')
@add_common_options
@click.option('--format', '-f', type=click.Choice(['csv', 'excel', 'json', 'markdown']),
              help='输出格式，默认根据扩展名自动判断')
@click.option('--no-details', is_flag=True, help='只导出元数据，不导出文件明细')
@click.option('--report', is_flag=True, help='导出完整报告（仅 JSON 和 Markdown 格式）')
def export(directory, output_file, recursive, extensions, min_size, max_size,
           date_from, date_to, date_type, format, no_details, report):
    """导出文件目录清单和整理报告
    
    DIRECTORY: 要导出的目录路径
    
    支持格式：
    
      csv       CSV 表格（默认）
    
      excel     Excel 表格（.xlsx）
    
      json      JSON 格式，支持完整报告
    
      markdown  Markdown 格式，支持完整报告
    
    示例：
    
      doctidy export ./docs -o 文件清单.csv
    
      doctidy export ./docs -o 文件清单.xlsx -f excel
    
      doctidy export ./docs -o 整理报告.md --report
    
      doctidy export ./docs -o 数据.json --report
    """
    try:
        ext_list = list(extensions) if extensions else None
        
        result = export_command(
            directory=directory,
            output_file=output_file,
            recursive=recursive,
            extensions=ext_list,
            format=format,
            include_details=not no_details,
            include_report=report,
            min_size=min_size,
            max_size=max_size,
            date_from=date_from,
            date_to=date_to,
            date_type=date_type
        )
        print_export_result(result)
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--id', 'history_id', help='指定要撤销的操作ID')
def undo(history_id):
    """撤销上次操作
    
    支持撤销的操作：rename、classify、merge
    
    示例：
    
      doctidy undo          # 撤销最近一次操作
    
      doctidy undo --id rename_20240115_103000
    """
    try:
        results = undo_operation(history_id)
        
        click.echo("=" * 70)
        click.echo("撤销操作完成")
        click.echo("=" * 70)
        
        if results['success']:
            click.echo(f"\n成功撤销 {len(results['success'])} 项:")
            for item in results['success']:
                click.echo(f"  ✓ {item}")
        
        if results['skipped']:
            click.echo(f"\n跳过 {len(results['skipped'])} 项:")
            for item in results['skipped']:
                click.echo(f"  - {item}")
        
        if results['failed']:
            click.echo(f"\n失败 {len(results['failed'])} 项:", err=True)
            for item in results['failed']:
                click.echo(f"  ✗ {item}", err=True)
        
        click.echo("")
        
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--limit', '-n', default=10, help='显示最近多少条记录')
def history(limit):
    """查看操作历史
    
    示例：
    
      doctidy history
    
      doctidy history -n 5
    """
    try:
        histories = get_history(limit=limit)
        
        if not histories:
            click.echo("暂无操作历史")
            return
        
        click.echo("=" * 70)
        click.echo(f"操作历史（最近 {len(histories)} 条）")
        click.echo("=" * 70)
        click.echo("")
        
        for h in histories:
            status = "已撤销" if h.get('undone') else "正常"
            changes_count = len(h.get('changes', []))
            click.echo(f"ID: {h['id']}")
            click.echo(f"类型: {h['type']}  |  状态: {status}  |  变动: {changes_count} 项")
            click.echo(f"时间: {h['timestamp']}")
            if h.get('description'):
                click.echo(f"说明: {h['description']}")
            click.echo("-" * 70)
        
        click.echo("")
        click.echo(f"使用 doctidy undo [--id <ID>] 撤销操作")
        
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
