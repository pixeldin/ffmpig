import argparse
import importlib.util
import sys
from pathlib import Path

import report_store


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "visit_stats.db"
DEFAULT_CHFS_URL = "http://192.168.28.67:9527"


def load_analyze_v2():
    module_path = Path(__file__).resolve().parent / "analyze-v2.py"
    spec = importlib.util.spec_from_file_location("analyze_v2_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def to_legacy_access_map(visit_summary):
    return {
        file_key: ",".join(value.get("times", []))
        for file_key, value in visit_summary.items()
    }


def build_from_db(db_path, chfs_root, chfs_base_url=DEFAULT_CHFS_URL):
    analyze_v2 = load_analyze_v2()
    conn = report_store.connect(db_path)
    try:
        report_store.ensure_schema(conn)
        visit_summary = report_store.query_visit_summary(conn)
        access_map = to_legacy_access_map(visit_summary)
    finally:
        conn.close()

    print("=" * 60)
    print("文件访问日志报表生成工具 (SQLite)")
    print("=" * 60)
    print(f"数据库: {Path(db_path).resolve()}")
    print(f"CHFS 根目录: {chfs_root}")
    print(f"CHFS 基础 URL: {chfs_base_url}")
    print(f"数据库访问文件数: {len(visit_summary)}")
    print("=" * 60)

    print("\n[1/3] 扫描 CHFS 共享目录...")
    file_map = analyze_v2.scan_chfs_directory(chfs_root)

    print("\n[2/3] 合并数据库访问记录...")
    merged_data = analyze_v2.merge_data(file_map, access_map)
    print(f"合并完成，共 {len(merged_data)} 个文件")
    print(f"  - 已访问: {sum(1 for v in merged_data.values() if v['count'] > 0)}")
    print(f"  - 未访问: {sum(1 for v in merged_data.values() if v['count'] == 0)}")
    print(f"  - 有预览图: {sum(1 for v in merged_data.values() if v['preview'])}")

    print("\n[3/3] 生成前端报表...")
    analyze_v2.generate_statistics(merged_data, chfs_base_url)
    print("\n完成！")


def build_parser():
    parser = argparse.ArgumentParser(description="从 SQLite 访问记录生成 CHFS 报表数据")
    parser.add_argument(
        "db_path",
        help=f"SQLite 数据库路径，例如 {DEFAULT_DB_PATH}",
    )
    parser.add_argument("chfs_root", help="CHFS 共享目录根路径，例如 I:/files")
    parser.add_argument(
        "chfs_base_url",
        nargs="?",
        default=DEFAULT_CHFS_URL,
        help=f"CHFS 访问基础 URL，默认 {DEFAULT_CHFS_URL}",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    build_from_db(args.db_path, args.chfs_root, args.chfs_base_url)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"生成报表失败: {exc}", file=sys.stderr)
        sys.exit(1)
