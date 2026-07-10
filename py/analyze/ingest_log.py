import argparse
import hashlib
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import report_store


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "visit_stats.db"
TIME_PATTERN = re.compile(r"\[(.*?)\]")
PATH_PATTERN = re.compile(r'"([^"]*)"')
STATUS_PATTERN = re.compile(r"\]\s+(\d{3})\s+")
IGNORED_SUFFIXES = (".mk.txt", ".srt")
IGNORED_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


def convert_to_timestamp(input_time):
    try:
        cleaned_time = re.sub(r"[+\-][0-9]{2}:[0-9]{2}", "", input_time).replace("T", " ")
        return int(datetime.strptime(cleaned_time, "%Y-%m-%d %H:%M:%S").timestamp())
    except ValueError:
        return None


def normalize_file_key(raw_path):
    path_without_query = raw_path.split("?", 1)[0].strip()
    if "/FILES/" not in path_without_query:
        return None

    file_key = path_without_query.split("/FILES/", 1)[1].replace("\\", "/").strip("/")
    file_key = unquote(file_key)
    lower_key = file_key.lower()

    if not file_key:
        return None
    if "wind-sum" in lower_key.split("/"):
        return None
    if lower_key.endswith("desktop.ini"):
        return None
    if lower_key.endswith(IGNORED_SUFFIXES):
        return None
    if lower_key.endswith(IGNORED_IMAGE_SUFFIXES):
        return None
    return file_key


def parse_log_line(line):
    if "vvv=1" not in line:
        return None

    time_match = TIME_PATTERN.search(line)
    path_match = PATH_PATTERN.search(line)
    if not time_match or not path_match:
        return None

    access_time = time_match.group(1)
    raw_path = path_match.group(1)
    access_ts = convert_to_timestamp(access_time)
    file_key = normalize_file_key(raw_path)
    if access_ts is None or file_key is None:
        return None

    status_match = STATUS_PATTERN.search(line)
    status_code = int(status_match.group(1)) if status_match else None
    raw_line = line.rstrip("\r\n")
    event_source = f"{access_time}|{status_code}|{raw_path}|{raw_line}"
    event_key = hashlib.sha256(event_source.encode("utf-8", errors="replace")).hexdigest()

    return {
        "event_key": event_key,
        "file_key": file_key,
        "access_time": access_time,
        "access_ts": access_ts,
        "status_code": status_code,
        "raw_path": raw_path,
        "raw_line": raw_line,
    }


def file_fingerprint(log_path, file_size):
    stat = os.stat(log_path)
    seed = f"{file_size}:{int(stat.st_mtime)}"
    if file_size <= 0:
        return seed

    with open(log_path, "rb") as file:
        head = file.read(4096)
        if file_size > 4096:
            file.seek(max(0, file_size - 4096))
            tail = file.read(4096)
        else:
            tail = b""
    digest = hashlib.sha256(head + tail).hexdigest()
    return f"{seed}:{digest}"


def ingest_from_offset(conn, log_path, offset):
    stats = {
        "read": 0,
        "matched": 0,
        "raw_inserted": 0,
        "visit_inserted": 0,
        "skipped": 0,
    }

    with open(log_path, "rb") as file:
        file.seek(offset)
        while True:
            line_offset = file.tell()
            raw_line = file.readline()
            if not raw_line:
                break

            # 避免在日志仍在写入时处理半行；下次从半行起点重读。
            if not raw_line.endswith((b"\n", b"\r")):
                file.seek(line_offset)
                break

            stats["read"] += 1
            line = raw_line.decode("utf-8", errors="replace")
            event = parse_log_line(line)
            if event is None:
                stats["skipped"] += 1
                continue

            stats["matched"] += 1
            raw_inserted = report_store.insert_raw_event(conn, event)
            if raw_inserted:
                stats["raw_inserted"] += 1
                if report_store.maybe_insert_file_visit(conn, event):
                    stats["visit_inserted"] += 1

        stats["offset"] = file.tell()

    return stats


def resolve_start_offset(conn, log_path, mode):
    if mode == "init":
        return 0

    state = report_store.get_log_state(conn, str(log_path))
    if state is None:
        return 0

    file_size = log_path.stat().st_size
    saved_offset = int(state["offset"])
    if file_size < saved_offset:
        print("检测到日志文件小于已保存 offset，按日志截断/轮转处理，从头读取。")
        return 0
    return saved_offset


def run(mode, log_path, db_path):
    log_path = Path(log_path).resolve()
    db_path = Path(db_path).resolve()

    if not log_path.exists():
        raise FileNotFoundError(f"日志文件不存在: {log_path}")

    conn = report_store.connect(db_path)
    try:
        report_store.ensure_schema(conn)
        with report_store.transaction(conn):
            offset = resolve_start_offset(conn, log_path, mode)
            stats = ingest_from_offset(conn, log_path, offset)
            file_size = log_path.stat().st_size
            fingerprint = file_fingerprint(log_path, file_size)
            report_store.save_log_state(
                conn,
                str(log_path),
                stats["offset"],
                file_size,
                fingerprint,
            )
    finally:
        conn.close()

    print("=" * 60)
    print(f"模式: {mode}")
    print(f"日志: {log_path}")
    print(f"数据库: {db_path}")
    print(f"读取行数: {stats['read']}")
    print(f"命中 vvv=1 事件: {stats['matched']}")
    print(f"新增原始事件: {stats['raw_inserted']}")
    print(f"新增有效访问: {stats['visit_inserted']}")
    print(f"跳过行数: {stats['skipped']}")
    print(f"保存 offset: {stats['offset']}")
    print("=" * 60)
    return stats


def build_parser():
    parser = argparse.ArgumentParser(description="增量同步 Nginx CHFS 访问日志到 SQLite")
    parser.add_argument("mode", choices=["init", "tail"], help="init 从头导入；tail 从上次 offset 继续读取")
    parser.add_argument("log_path", help="Nginx access_chfs.log 路径")
    parser.add_argument(
        "db_path",
        nargs="?",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite 数据库路径，默认 {DEFAULT_DB_PATH}",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    run(args.mode, args.log_path, args.db_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"同步失败: {exc}", file=sys.stderr)
        sys.exit(1)
