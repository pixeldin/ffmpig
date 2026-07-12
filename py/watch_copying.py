import datetime
import json
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk

import pyperclip
from colorama import Back, Fore, Style, init

try:
    import keyboard as global_keyboard
except ImportError:
    global_keyboard = None


init()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
STATE_PATH = os.path.join(LOG_DIR, "watch_copying-state.json")
PREVIEW_POSITION_PATH = os.path.join(LOG_DIR, "watch_copying-preview.json")
POLL_INTERVAL = 0.15
PREVIEW_WIDTH = 420
PREVIEW_HEIGHT = 132
PREVIEW_MARGIN_X = 28
PREVIEW_MARGIN_Y = 72
LOG_RETENTION_DAYS = 7

COMMANDS = {
    "undo",
    "u",
    "undo_pair",
    "up",
    "clear",
    "status",
    "st",
    "end",
    "finish",
}
EXIT_COMMANDS = {"quit", "exit", "q"}


def print_red(text):
    print(Style.BRIGHT + Fore.RED + text + Style.RESET_ALL)


def print_green(text):
    print(Style.BRIGHT + "\033[7;49;32m" + text + "\033[39m" + Style.RESET_ALL)


def print_yellow(text):
    print(Style.BRIGHT + Fore.YELLOW + Back.CYAN + text + Style.RESET_ALL)


def print_cyan(text):
    print(Style.BRIGHT + Fore.CYAN + text + Style.RESET_ALL)


def print_hl(text):
    print(Style.BRIGHT + Back.CYAN + text + Style.RESET_ALL)


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def log_path_for_today():
    today = datetime.datetime.now().strftime("%Y%m%d")
    return os.path.join(LOG_DIR, f"watch_copying-{today}.jsonl")


def append_log(event, **payload):
    ensure_log_dir()
    record = {"time": now_iso(), "event": event, **payload}
    with open(log_path_for_today(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def cleanup_old_logs(retention_days=LOG_RETENTION_DAYS):
    ensure_log_dir()
    cutoff = datetime.date.today() - datetime.timedelta(days=retention_days - 1)

    for filename in os.listdir(LOG_DIR):
        match = re.fullmatch(r"watch_copying-(\d{8})\.jsonl", filename)
        if not match:
            continue

        try:
            file_date = datetime.datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            continue

        if file_date >= cutoff:
            continue

        path = os.path.join(LOG_DIR, filename)
        try:
            os.remove(path)
        except OSError as exc:
            append_log("cleanup_log_failed", path=path, error=str(exc))


def save_state(state):
    ensure_log_dir()
    tmp_path = STATE_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, STATE_PATH)


def remove_state():
    try:
        os.remove(STATE_PATH)
    except FileNotFoundError:
        pass


def convert_time_string(time_str):
    nums = re.findall(r"\d+", time_str)
    if len(nums) == 1:
        seconds = int(nums[0])
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
    elif len(nums) == 2:
        minutes = int(nums[0])
        seconds = int(nums[1])
        hours, minutes = divmod(minutes, 60)
    elif len(nums) == 3:
        hours = int(nums[0])
        minutes = int(nums[1])
        seconds = int(nums[2])
    else:
        return ""

    return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)


def parse_time_seconds(time_str):
    h, m, s = [int(part) for part in time_str.split(":")]
    return h * 3600 + m * 60 + s


def join_array_elements_with_sp(arr):
    output = ""
    count_plus = 0
    max_plus = 2

    for i in range(0, len(arr), 2):
        if count_plus == max_plus:
            output += "\\\n"
            count_plus = 0

        if i > 0:
            output += "+"

        output += arr[i]
        if i + 1 < len(arr):
            output += ","
            output += arr[i + 1]

        count_plus += 1

    return output


def format_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return "{}小时{}分{}秒".format(h, m, s)
    if m > 0:
        return "{}分{}秒".format(m, s)
    return "{}秒".format(s)


def windows_path_to_linux_and_filename(filepath):
    abs_path = os.path.normpath(os.path.abspath(filepath))
    linux_path = "/" + abs_path.replace("\\", "/").replace(":", "").lower()
    filename = os.path.basename(abs_path)
    dir_path = os.path.dirname(linux_path)
    return dir_path, filename


def is_valid_path(path):
    if os.name == "nt":
        pattern = r'^[a-zA-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*$'
    else:
        pattern = r"^\/(?:[^\/\0]+\/)*[^\/\0]*$"

    return True if re.match(pattern, path) else False


class PreviewOverlay:
    def __init__(self):
        self.messages = queue.Queue()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, name="clip-preview-overlay", daemon=True)
        self.failed = False

    def start(self):
        self.thread.start()
        if not self.ready.wait(timeout=2):
            self.failed = True
            print_yellow("预览窗口启动超时，将仅使用终端输出")

    def update(self, title, lines):
        if self.failed:
            return
        self.messages.put(("update", title, lines))

    def close(self):
        if self.failed:
            return
        self.messages.put(("close", "", []))

    def _run(self):
        try:
            root = tk.Tk()
            root.withdraw()
            root.title("Clip Preview")
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.configure(bg="#181818")

            x, y = self._load_position(root)
            root.geometry(f"{PREVIEW_WIDTH}x{PREVIEW_HEIGHT}+{x}+{y}")

            frame = tk.Frame(root, bg="#181818", padx=16, pady=12)
            frame.pack(fill="both", expand=True)

            title_var = tk.StringVar(value="等待视频路径")
            line1_var = tk.StringVar(value="复制视频路径后开始记录")
            line2_var = tk.StringVar(value="Ctrl+Alt+Z 撤销, Ctrl+Alt+S 结束")
            line3_var = tk.StringVar(value="")

            title_label = tk.Label(
                frame,
                textvariable=title_var,
                bg="#181818",
                fg="#ffffff",
                font=("Microsoft YaHei UI", 12, "bold"),
                anchor="w",
            )
            title_label.pack(fill="x")
            line1_label = tk.Label(
                frame,
                textvariable=line1_var,
                bg="#181818",
                fg="#e8e8e8",
                font=("Microsoft YaHei UI", 10),
                anchor="w",
            )
            line1_label.pack(fill="x", pady=(8, 0))
            line2_label = tk.Label(
                frame,
                textvariable=line2_var,
                bg="#181818",
                fg="#cfcfcf",
                font=("Microsoft YaHei UI", 10),
                anchor="w",
            )
            line2_label.pack(fill="x", pady=(4, 0))
            line3_label = tk.Label(
                frame,
                textvariable=line3_var,
                bg="#181818",
                fg="#8cc8ff",
                font=("Consolas", 9),
                anchor="w",
            )
            line3_label.pack(fill="x", pady=(8, 0))

            drag = {"x": 0, "y": 0}

            def drag_start(event):
                drag["x"] = event.x_root - root.winfo_x()
                drag["y"] = event.y_root - root.winfo_y()
                self._set_no_activate(root)

            def drag_move(event):
                next_x = event.x_root - drag["x"]
                next_y = event.y_root - drag["y"]
                root.geometry(f"+{next_x}+{next_y}")
                self._set_no_activate(root)

            def drag_end(_event):
                self._save_position(root.winfo_x(), root.winfo_y())
                self._set_no_activate(root)

            for widget in (root, frame, title_label, line1_label, line2_label, line3_label):
                widget.bind("<ButtonPress-1>", drag_start)
                widget.bind("<B1-Motion>", drag_move)
                widget.bind("<ButtonRelease-1>", drag_end)
                widget.configure(cursor="fleur")

            root.update_idletasks()
            self._set_no_activate(root)
            root.deiconify()
            self._set_no_activate(root)
            self.ready.set()

            def pump():
                while True:
                    try:
                        event, title, lines = self.messages.get_nowait()
                    except queue.Empty:
                        break

                    if event == "close":
                        root.destroy()
                        return

                    padded = list(lines[:3]) + [""] * (3 - len(lines[:3]))
                    title_var.set(title)
                    line1_var.set(padded[0])
                    line2_var.set(padded[1])
                    line3_var.set(padded[2])
                    self._set_no_activate(root)

                root.after(80, pump)

            root.after(80, pump)
            root.mainloop()
        except Exception as exc:
            self.failed = True
            self.ready.set()
            print_red(f"预览窗口启动失败: {exc}")
            append_log("preview_failed", error=str(exc))

    def _load_position(self, root):
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        default_x = max(0, screen_width - PREVIEW_WIDTH - PREVIEW_MARGIN_X)
        default_y = max(0, screen_height - PREVIEW_HEIGHT - PREVIEW_MARGIN_Y)

        try:
            with open(PREVIEW_POSITION_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
            x = int(state.get("x", default_x))
            y = int(state.get("y", default_y))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return default_x, default_y

        x = min(max(0, x), max(0, screen_width - 80))
        y = min(max(0, y), max(0, screen_height - 60))
        return x, y

    def _save_position(self, x, y):
        try:
            ensure_log_dir()
            with open(PREVIEW_POSITION_PATH, "w", encoding="utf-8") as f:
                json.dump({"x": x, "y": y, "updated_at": now_iso()}, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            append_log("preview_position_save_failed", error=str(exc), x=x, y=y)

    def _set_no_activate(self, root):
        if os.name != "nt":
            return

        try:
            import ctypes

            hwnd = root.winfo_id()
            user32 = ctypes.windll.user32
            gwl_exstyle = -20
            ws_ex_toolwindow = 0x00000080
            ws_ex_noactivate = 0x08000000
            hwnd_topmost = -1
            swp_nosize = 0x0001
            swp_nomove = 0x0002
            swp_noactivate = 0x0010
            swp_showwindow = 0x0040

            style = user32.GetWindowLongW(hwnd, gwl_exstyle)
            style |= ws_ex_toolwindow | ws_ex_noactivate
            user32.SetWindowLongW(hwnd, gwl_exstyle, style)
            user32.SetWindowPos(
                hwnd,
                hwnd_topmost,
                0,
                0,
                0,
                0,
                swp_nomove | swp_nosize | swp_noactivate | swp_showwindow,
            )
        except Exception as exc:
            append_log("preview_no_activate_failed", error=str(exc))


class ClipRecorder:
    def __init__(self, preview=None):
        self.lock = threading.RLock()
        self.preview = preview
        self.active = False
        self.dir_path = ""
        self.filename = ""
        self.times = []
        self.tmp_path = ""

    def load_state(self):
        if not os.path.exists(STATE_PATH):
            return

        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print_red(f"读取恢复状态失败: {exc}")
            append_log("state_load_failed", error=str(exc))
            return

        if not state.get("active"):
            return

        with self.lock:
            self.active = True
            self.dir_path = state.get("dir_path", "")
            self.filename = state.get("filename", "")
            self.times = list(state.get("times", []))

        print_yellow(f"已恢复未结束记录: {self.filename}, 已记录 {len(self.times) // 2} 段")
        self.print_status()
        append_log("restore_state", filename=self.filename, dir_path=self.dir_path, times=self.times)

    def persist_state(self):
        state = {
            "active": self.active,
            "dir_path": self.dir_path,
            "filename": self.filename,
            "times": self.times,
            "updated_at": now_iso(),
        }
        save_state(state)

    def start_video(self, location):
        with self.lock:
            self.dir_path, self.filename = windows_path_to_linux_and_filename(location)
            self.times = []
            self.active = True
            self.persist_state()

        print("记录视频: " + self.filename)
        print_green("准备获取视频片段...")
        append_log("start_video", location=location, filename=self.filename, dir_path=self.dir_path)
        self._preview(
            "记录视频",
            [
                self.filename,
                "等待 From 时间点",
                "片段: 0 | 总时长: 0秒",
            ],
        )

        try:
            pyperclip.copy("")
        except pyperclip.PyperclipException as exc:
            print_red(f"清空剪贴板失败: {exc}")

    def add_time(self, time_value):
        with self.lock:
            if not self.active:
                return

            if self.times and self.times[-1] == time_value:
                return

            if len(self.times) % 2 == 1:
                start = self.times[-1]
                start_seconds = parse_time_seconds(start)
                end_seconds = parse_time_seconds(time_value)
                if end_seconds <= start_seconds:
                    print_red(f"忽略无效结束时间: {time_value} <= {start}")
                    append_log(
                        "reject_time",
                        filename=self.filename,
                        value=time_value,
                        reason="end_before_or_equal_start",
                        start=start,
                    )
                    self._toast("Time rejected", f"{time_value} <= {start}", 1.8)
                    return

                self.times.append(time_value)
                diff_seconds = end_seconds - start_seconds
                total_s = self.total_seconds_locked()
                self.persist_state()

                print(
                    "To: "
                    + time_value
                    + " 当前片段: "
                    + format_time(diff_seconds)
                    + ", 总时长: "
                    + format_time(total_s)
                )
                append_log(
                    "add_time",
                    filename=self.filename,
                    value=time_value,
                    role="to",
                    segment_seconds=diff_seconds,
                    total_seconds=total_s,
                    times=self.times,
                )
                self._toast(
                    "End",
                    time_value + " 当前片段: " + format_time(diff_seconds) + ", 总时长: " + format_time(total_s),
                    2.5,
                )
            else:
                self.times.append(time_value)
                self.persist_state()
                print("From: " + time_value, end=" ")
                sys.stdout.flush()
                append_log("add_time", filename=self.filename, value=time_value, role="from", times=self.times)
                self._toast("From", time_value, 1.1)

    def undo_last(self):
        with self.lock:
            if not self.active or not self.times:
                print_yellow("没有可撤销的时间点")
                return

            removed = self.times.pop()
            total_s = self.total_seconds_locked()
            self.persist_state()
            print_yellow(f"已撤销时间点: {removed}, 当前总时长: {format_time(total_s)}")
            append_log("undo", filename=self.filename, removed=[removed], times=self.times, total_seconds=total_s)
            self._toast("Undo", removed, 1.5)

    def undo_pair(self):
        with self.lock:
            if not self.active or not self.times:
                print_yellow("没有可撤销的片段")
                return

            remove_count = 1 if len(self.times) % 2 == 1 else 2
            removed = self.times[-remove_count:]
            del self.times[-remove_count:]
            total_s = self.total_seconds_locked()
            self.persist_state()
            print_yellow(f"已撤销片段: {','.join(removed)}, 当前总时长: {format_time(total_s)}")
            append_log("undo_pair", filename=self.filename, removed=removed, times=self.times, total_seconds=total_s)
            self._toast("Undo pair", ",".join(removed), 1.8)

    def clear(self):
        with self.lock:
            if not self.active:
                print_yellow("当前没有正在记录的视频")
                return

            removed = self.times
            self.times = []
            self.persist_state()
            print_yellow("已清空当前视频的片段记录")
            append_log("clear", filename=self.filename, removed=removed)
            self._toast("Clear", self.filename, 1.5)

    def finish_video(self):
        with self.lock:
            if not self.active:
                print_yellow("当前没有正在记录的视频")
                return

            complete_times = self.complete_times_locked()
            pending = self.times[len(complete_times):]
            total_s = self.total_seconds_locked()
            segment_count = len(complete_times) // 2
            command = self.cut_command_locked(complete_times)
            final_output = self.final_output_locked(complete_times)

            print_red(
                "=================记录结束, 视频: "
                + self.filename
                + " 总时长: "
                + format_time(total_s)
                + ", 组合指令如下○( ＾-＾)。o O 0"
            )
            if pending:
                print_red("存在未成对的起始时间，已从最终命令中排除: " + ",".join(pending))

            if complete_times:
                print_hl(final_output)
                self.tmp_path = self.dir_path
                try:
                    pyperclip.copy(final_output)
                    print_green("已复制完整 cut 内容到剪贴板")
                except pyperclip.PyperclipException as exc:
                    print_red(f"复制 cut 内容到剪贴板失败: {exc}")
                    append_log("copy_final_output_failed", error=str(exc), filename=self.filename)
            else:
                print_red("没有完整片段，未生成有效 cut 命令")
            print_red("=======================================================================================")

            append_log(
                "end_video",
                filename=self.filename,
                dir_path=self.dir_path,
                times=self.times,
                complete_times=complete_times,
                pending=pending,
                total_seconds=total_s,
                segment_count=segment_count,
                command=command if complete_times else "",
                final_output=final_output if complete_times else "",
            )
            self._preview(
                "记录结束",
                [
                    f"{self.filename}",
                    f"片段: {segment_count} | 总时长: {format_time(total_s)}",
                    "等待下一个视频路径",
                ],
            )

            self.active = False
            self.dir_path = ""
            self.filename = ""
            self.times = []
            remove_state()
            print_green("Well done~ 请输入处理视频名称(包括路径), ○( ＾-＾)!…")

    def prepare_exit(self):
        with self.lock:
            if self.active:
                self.persist_state()
                total_s = self.total_seconds_locked()
                segment_count = len(self.complete_times_locked()) // 2
                print_yellow(
                    f"程序退出，已保存未结束记录: {self.filename}, 片段: {segment_count}, 总时长: {format_time(total_s)}"
                )
                self._preview(
                    "已保存并退出",
                    [
                        self.filename,
                        f"片段: {segment_count} | 总时长: {format_time(total_s)}",
                        "下次启动自动恢复",
                    ],
                )
                append_log(
                    "graceful_exit",
                    active=True,
                    filename=self.filename,
                    times=self.times,
                    total_seconds=total_s,
                    segment_count=segment_count,
                )
                return

            print_green("程序退出")
            self._preview("程序退出", ["当前没有正在记录的视频", "", ""])
            append_log("graceful_exit", active=False)

    def print_status(self):
        with self.lock:
            if not self.active:
                print_yellow("当前没有正在记录的视频")
                return

            total_s = self.total_seconds_locked()
            complete_times = self.complete_times_locked()
            segment_lines = self.segment_status_lines_locked()
            print_cyan(f"记录视频: {self.filename}")
            if segment_lines:
                for line in segment_lines:
                    print(line)
            else:
                print_yellow("还没有完整片段")
            if len(self.times) % 2 == 1:
                print_yellow("等待结束时间: From " + self.times[-1])
            print_cyan(f"完整片段: {len(complete_times) // 2}, 总时长: {format_time(total_s)}")
            if complete_times:
                print_hl(self.cut_command_locked(complete_times))

            if self.times and len(self.times) % 2 == 1:
                line1 = f"等待 To: {self.times[-1]} -> ..."
            elif len(self.times) >= 2:
                line1 = f"最后片段: {self.times[-2]} -> {self.times[-1]}"
            else:
                line1 = "等待 From 时间点"

            self._preview(
                "当前状态",
                [
                    line1,
                    f"片段: {len(complete_times) // 2} | 总时长: {format_time(total_s)}",
                    self.filename,
                ],
            )

            append_log(
                "status",
                filename=self.filename,
                times=self.times,
                total_seconds=total_s,
                segment_count=len(complete_times) // 2,
                segment_lines=segment_lines,
            )

    def handle_command(self, command):
        normalized = command.strip().lower()
        if normalized in {"undo", "u"}:
            self.undo_last()
        elif normalized in {"undo_pair", "up"}:
            self.undo_pair()
        elif normalized == "clear":
            self.clear()
        elif normalized in {"status", "st"}:
            self.print_status()
        elif normalized in {"end", "finish"}:
            self.finish_video()

    def total_seconds_locked(self):
        total = 0
        complete_times = self.complete_times_locked()
        for i in range(0, len(complete_times), 2):
            total += parse_time_seconds(complete_times[i + 1]) - parse_time_seconds(complete_times[i])
        return total

    def complete_times_locked(self):
        complete_len = len(self.times) - (len(self.times) % 2)
        return self.times[:complete_len]

    def cut_command_locked(self, complete_times=None):
        if complete_times is None:
            complete_times = self.complete_times_locked()
        return "cut_with_src.sh -o " + self.filename + " -m " + join_array_elements_with_sp(complete_times)

    def final_output_locked(self, complete_times=None):
        if complete_times is None:
            complete_times = self.complete_times_locked()
        total_s = self.total_seconds_locked()
        segment_count = len(complete_times) // 2
        lines = [
            'jump "' + self.dir_path + '"',
            "# " + self.filename + ", 总时长:" + format_time(total_s) + ", 片段数量: " + str(segment_count),
            self.cut_command_locked(complete_times),
        ]
        return "\n".join(lines)

    def segment_status_lines_locked(self):
        lines = []
        complete_times = self.complete_times_locked()
        total = 0
        for i in range(0, len(complete_times), 2):
            start = complete_times[i]
            end = complete_times[i + 1]
            diff_seconds = parse_time_seconds(end) - parse_time_seconds(start)
            total += diff_seconds
            lines.append(
                f"From: {start} To: {end} 当前片段: {format_time(diff_seconds)}, 总时长: {format_time(total)}"
            )
        return lines

    def _preview(self, title, lines):
        if self.preview is not None:
            self.preview.update(title, lines)

    def _toast(self, title, message, duration):
        total_s = self.total_seconds_locked()
        segment_count = len(self.complete_times_locked()) // 2

        if title == "From" and self.times:
            self._preview(
                "From",
                [
                    f"等待 To: {self.times[-1]} -> ...",
                    f"片段: {segment_count} | 总时长: {format_time(total_s)}",
                    self.filename,
                ],
            )
            return

        if title == "End" and len(self.times) >= 2:
            start = self.times[-2]
            end = self.times[-1]
            diff_seconds = parse_time_seconds(end) - parse_time_seconds(start)
            self._preview(
                "当前片段",
                [
                    f"{start} -> {end} | {format_time(diff_seconds)}",
                    f"片段: {segment_count} | 总时长: {format_time(total_s)}",
                    self.filename,
                ],
            )
            return

        if title in {"Undo", "Undo pair", "Clear"}:
            if self.times and len(self.times) % 2 == 1:
                line1 = f"等待 To: {self.times[-1]} -> ..."
            elif len(self.times) >= 2:
                line1 = f"最后片段: {self.times[-2]} -> {self.times[-1]}"
            else:
                line1 = "等待 From 时间点"

            self._preview(
                title,
                [
                    line1,
                    f"片段: {segment_count} | 总时长: {format_time(total_s)}",
                    f"已处理: {message}",
                ],
            )
            return

        self._preview(
            title,
            [
                message,
                f"片段: {segment_count} | 总时长: {format_time(total_s)}",
                self.filename,
            ],
        )


def install_hotkeys(recorder, request_exit):
    if global_keyboard is None:
        print_yellow("未安装 keyboard 包，全局快捷键不可用；仍可复制 undo / undo_pair / status / end 作为命令")
        append_log("hotkeys_unavailable", reason="keyboard_package_missing")
        return

    hotkeys = {
        "ctrl+alt+z": recorder.undo_last,
        "ctrl+alt+x": recorder.undo_pair,
        "ctrl+alt+r": recorder.print_status,
        "ctrl+alt+s": recorder.finish_video,
        "ctrl+alt+q": request_exit,
    }

    try:
        for hotkey, callback in hotkeys.items():
            global_keyboard.add_hotkey(hotkey, callback)
    except Exception as exc:
        print_red(f"注册全局快捷键失败: {exc}")
        append_log("hotkeys_failed", error=str(exc))
        return

    print_cyan(
        "全局快捷键: Ctrl+Alt+Z 撤销时间点, Ctrl+Alt+X 撤销片段, Ctrl+Alt+R 状态, Ctrl+Alt+S 结束视频, Ctrl+Alt+Q 退出"
    )
    append_log("hotkeys_ready", hotkeys=list(hotkeys.keys()))


def handle_clipboard_text(recorder, clipboard_text, request_exit):
    text = clipboard_text.strip()
    if not text:
        return

    if text.lower() in EXIT_COMMANDS:
        request_exit()
        return

    if recorder.active and text.lower() in COMMANDS:
        recorder.handle_command(text)
        return

    if recorder.active:
        time_value = convert_time_string(text)
        if time_value:
            recorder.add_time(time_value)
        return

    if is_valid_path(text):
        recorder.start_video(text)


def main():
    ensure_log_dir()
    cleanup_old_logs()
    preview = PreviewOverlay()
    preview.start()
    stop_event = threading.Event()
    recorder = ClipRecorder(preview)

    def request_exit():
        recorder.prepare_exit()
        stop_event.set()

    recorder.load_state()
    install_hotkeys(recorder, request_exit)

    print_green("请输入处理视频名称(包括路径)：○( ＾皿＾)っ…")
    print_cyan("剪贴板命令: undo/u, undo_pair/up, status/st, clear, end/finish, quit/exit/q")

    last_clipboard_text = None
    try:
        last_clipboard_text = pyperclip.paste()
    except pyperclip.PyperclipException as exc:
        print_red(f"读取剪贴板失败: {exc}")
        append_log("clipboard_read_failed", error=str(exc))

    try:
        while not stop_event.is_set():
            try:
                try:
                    clipboard_text = pyperclip.paste()
                except pyperclip.PyperclipException as exc:
                    print_red(f"读取剪贴板失败: {exc}")
                    append_log("clipboard_read_failed", error=str(exc))
                    time.sleep(1)
                    continue

                if clipboard_text != last_clipboard_text:
                    last_clipboard_text = clipboard_text
                    handle_clipboard_text(recorder, clipboard_text, request_exit)

                time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                if recorder.active:
                    recorder.finish_video()
                    try:
                        last_clipboard_text = pyperclip.paste()
                    except pyperclip.PyperclipException:
                        last_clipboard_text = None
                    continue

                request_exit()
    finally:
        preview.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("程序已退出")
        sys.exit()
    except Exception as exc:
        append_log("crash", error=repr(exc))
        raise
