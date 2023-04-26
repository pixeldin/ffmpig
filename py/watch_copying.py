import pyperclip
import time
import datetime
from datetime import timedelta
from colorama import init, Fore, Style, Back
import re
import sys
import os

init()

def print_red(text):
    print(Fore.RED + text + Fore.RESET)

def print_green(text):
    print('\033[7;49;32m' + text + '\033[39m')

def print_cyan(text):
    print(Fore.CYAN + text + Fore.RESET)

def print_hl(text):
    print(Back.BLUE + Fore.YELLOW + text + Style.RESET_ALL)

def convert_time_string(time_str):
    # 首先，使用正则表达式匹配字符串中的所有数字
    nums = re.findall(r'\d+', time_str)
    if len(nums) == 1:  # 如果只有一个数字，则将其作为秒数处理
        seconds = int(nums[0])
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
    elif len(nums) == 2:  # 如果有两个数字，则将其作为分钟和秒钟处理
        minutes = int(nums[0])
        seconds = int(nums[1])
        hours, minutes = divmod(minutes, 60)
    elif len(nums) == 3:  # 如果有三个数字，则将其作为小时、分钟和秒钟处理
        hours = int(nums[0])
        minutes = int(nums[1])
        seconds = int(nums[2])
    else:
        return ''  # 其他情况返回空串

    # 格式化时间字符串，并返回结果
    return '{:02d}:{:02d}:{:02d}'.format(hours, minutes, seconds)

def join_array_elements(arr):
    output = ""

    for i in range(0, len(arr), 2):
        if i > 0:
            output += "+"
        output += arr[i]
        if i + 1 < len(arr):
            output += ","
            output += arr[i+1]

    return output

def format_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return '{}小时{}分{}秒'.format(h, m, s)
    elif m > 0:
        return '{}分{}秒'.format(m, s)
    else:
        return '{}秒'.format(s)

def windows_path_to_linux_and_filename(filepath):
    # 转换为绝对路径并标准化
    abs_path = os.path.normpath(os.path.abspath(filepath))

    # 替换反斜杠为正斜杠并将驱动器号转换为小写
    linux_path = '/' + abs_path.replace('\\', '/').replace(':', '').lower()

    # 提取文件名
    filename = os.path.basename(linux_path)

    # 提取目录路径
    dir_path = os.path.dirname(linux_path)

    return (dir_path, filename)

# 判断是否路径合法
def is_valid_path(path):
    """Check if a given string is a valid file or directory path."""
    if os.name == 'nt':
        # Windows path format: drive letter followed by colon, e.g. 'C:'
        pattern = r'^[a-zA-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*$'
    else:
        # Unix/Mac/Linux path format: starts with '/', e.g. '/path/to/file'
        pattern = r'^\/(?:[^\/\0]+\/)*[^\/\0]*$'

    return True if re.match(pattern, path) else False


print_green("请输入处理视频名称(包括路径)：")

while True:
    # location = input("请输入处理视频名称(包括路径)：")
    try:
        # 获取当前剪贴板中的内容
        pyperclip.waitForNewPaste()
        location = pyperclip.paste()

        if not is_valid_path(location) :
            continue

        # windows_path = r'E:\template\hello.mp4'
        (dir_path, filename) = windows_path_to_linux_and_filename(location)
        print_green("记录视频: " + filename)
        print_cyan("准备获取视频片段...")
        clipboard_history = []

        pyperclip.copy('')

        i = 0
        time_format = "%H:%M:%S"
        total_s = 0

        try:
            while True:
                # 获取当前剪贴板中的内容
                pyperclip.waitForNewPaste()
                # eg: 00:00:03,00:00:41 00:01:03,00:01:11
                clipboard_content = pyperclip.paste()
                clipboard_content = convert_time_string(clipboard_content)

                # 如果该内容已经被记录则跳过
                if len(clipboard_content) == 0 or clipboard_content in clipboard_history :
                    continue

                # 将该内容添加到已记录的剪贴板内容列表中
                if i % 2 == 0:
                    print("From: "+clipboard_content, end=' ')
                    sys.stdout.flush()  # 刷新输出缓冲区
                    # 将时间字符串转换为datetime对象
                    from_ts = datetime.datetime.strptime(clipboard_content, time_format)
                else:
                    print("To: "+clipboard_content)
                    to_ts = datetime.datetime.strptime(clipboard_content, time_format)
                    # 计算时间差并输出相差的秒数
                    diff_seconds = (to_ts - from_ts).seconds
                    total_s = total_s + diff_seconds

                    print_green("当前片段: " + format_time(diff_seconds) + ",总时长: " + format_time(total_s))

                i += 1
                clipboard_history.append(clipboard_content)
        except KeyboardInterrupt:
            # 用户按下Ctrl+C结束程序时，打印所有已记录的剪贴板内容
            # string_to_print = "\n".join(clipboard_history)
            print_cyan("===========记录结束, 视频: " + filename +" 总时长: " + format_time(total_s) + ", 组合指令:")
            print("cd " + dir_path)
            print_hl("cut_with_src.sh -o " + filename + " -m " + join_array_elements(clipboard_history))
            print_red("-----------------------------------------------------")
            print_green("请输入处理视频名称(包括路径)：")
    except KeyboardInterrupt as e:
        print('Outside watch exception：', e)