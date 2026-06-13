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
from .history import get_history, undo_operation, preview_undo, undo_partial
from .config import load_config, init_config, save_config, CONFIG_FILE


common_options = [
    click.option('--recursive/--no-recursive', default=True, help='是否递归扫描子目录'),
    click.option('--extension', '-e', 'extensions', multiple=True, help='按扩展名筛选，可多次指定'),
    click.option('--min-size', help='最小文件大小，如 1MB、500KB'),
    click.option('--max-size', help='最大文件大小，如 100MB'),
    click.option('--date-from', help='起始日期，格式 YYYY-MM-DD'),
    click.option('--date-to', help='结束日期，格式 YYYY-MM-DD'),
    click.option('--date-type', type=click.Choice(['modified', 'created']), default='modified',
                 help='日期筛选使用修改时间还是创建时间'),
    click.option('--config', 'config_path', help='指定配置文件路径，默认使用 ~/.doctidy/config.json'),
]


def add_common_options(func):
    for option in reversed(common_options):
        func = option(func)
    return func


def confirm_execution(preview: bool, yes: bool, action_desc: str) -> bool:
    if preview:
        return False
    if yes:
        return True
    return click.confirm(f"\n确认执行以上 {action_desc}？", default=False)


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
    
      undo     撤销操作（支持预览和部分回滚）
    
      history  查看操作历史
    
    示例：
    
      doctidy scan ./docs --duplicates
    
      doctidy rename ./docs --pattern "{date}_{name}" -y
    
      doctidy classify ./docs -o ./sorted --method keyword -y
    
      doctidy merge ./pdfs -o ./merged --group-by keyword -k 合同,报告
    
      doctidy check ./docs
    
      doctidy export ./docs -o 目录清单.xlsx
    
      doctidy undo --preview
    
      doctidy undo --only 1,3,5
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
         date_from, date_to, date_type, config_path, find_dup, details):
    """扫描目录，查看文件清单，识别重复文件"""
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
            show_details=details,
            config_path=config_path
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
@click.option('--preview', '-P', is_flag=True, help='仅预览，不执行')
@click.option('--yes', '-y', is_flag=True, help='跳过确认直接执行')
def rename(directory, pattern, recursive, extensions, min_size, max_size,
           date_from, date_to, date_type, config_path, date_source, custom_date, 
           keywords, output_dir, preview, yes):
    """按日期、编号、关键词批量重命名
    
    命名模式变量：
    
      {date} {date-} {date_} {year} {month} {day} {number} {name} {keyword} {counter} {counter2}
    
    示例：
    
      doctidy rename ./docs -p "{date}_{name}" -y
    
      doctidy rename ./docs -p "{date-}_{name}" --preview
    
      doctidy rename ./docs -p "合同_{date}_{counter}" -k 合同
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
            preview=True,
            min_size=min_size,
            max_size=max_size,
            date_from=date_from,
            date_to=date_to,
            date_type=date_type,
            config_path=config_path
        )
        
        print_rename_result(result, preview=True)
        
        if not result['changes']:
            click.echo("\n无需重命名的文件。")
            return
        
        if confirm_execution(preview, yes, f"重命名 {result['renamed']} 个文件"):
            result = rename_command(
                directory=directory,
                pattern=pattern,
                recursive=recursive,
                extensions=ext_list,
                date_source=date_source,
                custom_date=custom_date,
                keywords=kw_list,
                output_dir=output_dir,
                preview=False,
                min_size=min_size,
                max_size=max_size,
                date_from=date_from,
                date_to=date_to,
                date_type=date_type,
                config_path=config_path
            )
            click.echo("")
            click.echo("=" * 70)
            click.echo(f"重命名完成: 成功 {sum(1 for c in result['changes'] if c.get('success'))} 个")
            click.echo("=" * 70)
        elif not preview:
            click.echo("已取消。")
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
@click.option('--preview', '-P', is_flag=True, help='仅预览，不执行')
@click.option('--yes', '-y', is_flag=True, help='跳过确认直接执行')
def classify(directory, output_dir, recursive, extensions, min_size, max_size,
             date_from, date_to, date_type, config_path, method, rules_file, rules, 
             date_format, copy, preview, yes):
    """按规则将文件移动到分类文件夹
    
    分类方式：keyword(关键词) / extension(扩展名) / date(日期) / all(综合)
    
    示例：
    
      doctidy classify ./docs -o ./sorted -y
    
      doctidy classify ./docs -o ./sorted --method extension --preview
    
      doctidy classify ./docs -o ./sorted -R "合同:合同,协议" --copy
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
            preview=True,
            min_size=min_size,
            max_size=max_size,
            date_from=date_from,
            date_to=date_to,
            date_type=date_type,
            config_path=config_path
        )
        
        print_classify_result(result, preview=True)
        
        if not result['changes']:
            click.echo("\n无需分类的文件。")
            return
        
        action = "复制" if copy else "移动"
        if confirm_execution(preview, yes, f"{action} {result['classified']} 个文件到 {len(result['categories'])} 个分类"):
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
                preview=False,
                min_size=min_size,
                max_size=max_size,
                date_from=date_from,
                date_to=date_to,
                date_type=date_type,
                config_path=config_path
            )
            click.echo("")
            click.echo("=" * 70)
            success_count = sum(1 for c in result['changes'] if c.get('success'))
            click.echo(f"分类完成: 成功 {action} {success_count} 个文件")
            click.echo("=" * 70)
        elif not preview:
            click.echo("已取消。")
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
@click.option('--preview', '-P', is_flag=True, help='仅预览，不执行')
@click.option('--yes', '-y', is_flag=True, help='跳过确认直接执行')
def merge(directory, output_dir, recursive, extensions, min_size, max_size,
          date_from, date_to, date_type, config_path, group_by, keywords, sort_by,
          output_pattern, overwrite, preview, yes):
    """合并同类 PDF 文件
    
    分组方式：keyword(关键词) / date(年月) / prefix(前缀) / parent(父目录)
    
    示例：
    
      doctidy merge ./pdfs -o ./merged --group-by keyword -k 合同 -k 报告 -y
    
      doctidy merge ./pdfs -o ./merged --group-by date --preview
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
            preview=True,
            min_size=min_size,
            max_size=max_size,
            date_from=date_from,
            date_to=date_to,
            date_type=date_type,
            config_path=config_path
        )
        
        print_merge_result(result, preview=True)
        
        if not result['changes']:
            click.echo("\n无可合并的 PDF 文件。")
            return
        
        if confirm_execution(preview, yes, f"合并 {result['merged_count']} 组 PDF"):
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
                preview=False,
                min_size=min_size,
                max_size=max_size,
                date_from=date_from,
                date_to=date_to,
                date_type=date_type,
                config_path=config_path
            )
            click.echo("")
            click.echo("=" * 70)
            success_count = sum(1 for c in result['changes'] if c.get('success'))
            click.echo(f"合并完成: 成功 {success_count} 组")
            click.echo("=" * 70)
        elif not preview:
            click.echo("已取消。")
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
@add_common_options
@click.option('--no-duplicates', 'no_dup', is_flag=True, help='不检查重复文件')
@click.option('--no-missing', 'no_miss', is_flag=True, help='不检查缺失附件')
def check(directory, recursive, extensions, min_size, max_size,
          date_from, date_to, date_type, config_path, no_dup, no_miss):
    """检查重复文件和缺失附件"""
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
            date_type=date_type,
            config_path=config_path
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
@click.option('--report', is_flag=True, help='导出整理报告（含汇总、重复、缺失等），默认只导出文件清单')
def export(directory, output_file, recursive, extensions, min_size, max_size,
           date_from, date_to, date_type, config_path, format, report):
    """导出文件目录清单或整理报告
    
    默认导出文件清单，加 --report 导出完整整理报告。
    """
    try:
        ext_list = list(extensions) if extensions else None
        
        result = export_command(
            directory=directory,
            output_file=output_file,
            recursive=recursive,
            extensions=ext_list,
            format=format,
            report_mode=report,
            min_size=min_size,
            max_size=max_size,
            date_from=date_from,
            date_to=date_to,
            date_type=date_type,
            config_path=config_path
        )
        print_export_result(result)
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--id', 'history_id', help='指定要撤销的操作ID')
@click.option('--preview', '-P', is_flag=True, help='仅预览将回退的内容，不执行撤销')
@click.option('--only', help='只回滚指定序号的变动，逗号分隔，如 --only 1,3,5')
def undo(history_id, preview, only):
    """撤销操作（支持预览和部分回滚）
    
    示例：
    
      doctidy undo                     # 撤销最近一次操作
    
      doctidy undo --preview           # 预览将回退的内容
    
      doctidy undo --only 1,3          # 只回滚第 1、3 项变动
    
      doctidy undo --id classify_xxx   # 撤销指定操作
    """
    try:
        if preview:
            result = preview_undo(history_id)
            click.echo("=" * 70)
            click.echo("撤销预览 - 以下内容将被回退:")
            click.echo("=" * 70)
            click.echo(f"\n操作: {result['type']}  |  时间: {result['timestamp']}")
            if result.get('description'):
                click.echo(f"说明: {result['description']}")
            click.echo(f"变动项: {result['total_changes']} 项\n")
            
            for i, item in enumerate(result['items'], 1):
                click.echo(f"  {i}. {item}")
            
            click.echo("")
            click.echo("使用 doctidy undo [--id <ID>] 执行撤销")
            click.echo("使用 doctidy undo --only <序号> 部分回滚")
            return
        
        if only:
            indices = [int(x.strip()) for x in only.split(',')]
            results = undo_partial(history_id, indices)
        else:
            results = undo_operation(history_id)
        
        action = "部分回滚" if only else "撤销操作"
        click.echo("=" * 70)
        click.echo(f"{action}完成")
        click.echo("=" * 70)
        
        if results['success']:
            click.echo(f"\n成功 {len(results['success'])} 项:")
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
@click.option('--details', '-D', is_flag=True, help='显示每条操作的变动详情')
def history(limit, details):
    """查看操作历史
    
    示例：
    
      doctidy history
    
      doctidy history -n 5 --details
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
            changes = h.get('changes', [])
            changes_count = len(changes)
            click.echo(f"ID: {h['id']}")
            click.echo(f"类型: {h['type']}  |  状态: {status}  |  变动: {changes_count} 项")
            click.echo(f"时间: {h['timestamp']}")
            if h.get('description'):
                click.echo(f"说明: {h['description']}")
            
            if details and changes:
                click.echo(f"变动详情:")
                for i, change in enumerate(changes, 1):
                    if h['type'] == 'rename':
                        click.echo(f"  {i}. {change.get('old_name', '')} → {change.get('new_name', '')}")
                    elif h['type'] == 'classify':
                        cat = change.get('category', '')
                        click.echo(f"  {i}. {change.get('old_name', '')} → [{cat}]")
                    elif h['type'] == 'merge':
                        click.echo(f"  {i}. 合并组 [{change.get('group', '')}] → {os.path.basename(change.get('merged_file', ''))}")
                    else:
                        click.echo(f"  {i}. {change}")
            
            click.echo("-" * 70)
        
        click.echo("")
        click.echo("使用 doctidy undo [--id <ID>] 撤销操作")
        click.echo("使用 doctidy undo --preview 预览回退内容")
        click.echo("使用 doctidy undo --only 1,3 部分回滚")
        
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--init', 'do_init', is_flag=True, help='初始化默认配置文件')
@click.option('--show', is_flag=True, help='显示当前配置')
@click.option('--path', is_flag=True, help='显示配置文件路径')
def config(do_init, show, path):
    """管理配置文件
    
    示例：
    
      doctidy config --init           # 初始化默认配置到 ~/.doctidy/config.json
    
      doctidy config --show           # 显示当前配置内容
    
      doctidy config --path           # 显示配置文件路径
    """
    try:
        if do_init:
            config_path = init_config()
            click.echo(f"配置文件已初始化: {config_path}")
            return
        
        if path:
            click.echo(f"配置文件路径: {CONFIG_FILE}")
            if CONFIG_FILE.exists():
                click.echo(f"状态: 已存在")
            else:
                click.echo(f"状态: 未创建（使用 --init 初始化）")
            return
        
        if show:
            cfg = load_config()
            click.echo("=" * 70)
            click.echo("当前配置")
            click.echo("=" * 70)
            
            click.echo("\n分类关键词规则:")
            for cat, kws in cfg.get('category_rules', {}).items():
                click.echo(f"  {cat}: {', '.join(kws)}")
            
            click.echo("\n扩展名分组:")
            for group, exts in cfg.get('extension_groups', {}).items():
                click.echo(f"  {group}: {', '.join(exts)}")
            
            click.echo("\n主文档识别模式:")
            for p in cfg.get('main_doc_patterns', []):
                click.echo(f"  - {p}")
            
            click.echo("\n附件检查模式:")
            for item in cfg.get('attachment_patterns', []):
                click.echo(f"  - {item.get('regex', '')} => {item.get('template', '')}")
            
            click.echo(f"\n扫描扩展名: {', '.join(cfg.get('scan_extensions', []))}")
            
            click.echo(f"\n配置文件: {CONFIG_FILE}")
            click.echo("")
            return
        
        click.echo("使用 --init, --show 或 --path 参数")
    except Exception as e:
        click.echo(f"错误: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
