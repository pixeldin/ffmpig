import pyperclip
import time
import datetime
from datetime import timedelta
import re
import sys

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

            print("当前片段: "+format_time(diff_seconds)+",总时长: "+format_time(total_s))

        i += 1
        clipboard_history.append(clipboard_content)
except KeyboardInterrupt:
    # 用户按下Ctrl+C结束程序时，打印所有已记录的剪贴板内容
	# for content in clipboard_history:
    # string_to_print = "\n".join(clipboard_history)
    print("\n复制列表结果:\n"+join_array_elements(clipboard_history))
    print("==总时长: "+format_time(total_s))
