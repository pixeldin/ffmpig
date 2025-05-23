import sys
import os
import re
from datetime import datetime
from collections import defaultdict

# 辅助函数：将日期时间字符串转为时间戳
def convert_to_timestamp(input_time):
    try:
        # 去掉时区部分（例如 +08:00）并替换 "T" 为 " "，将格式改为 "2025-01-08 11:23:19"
        cleaned_time = re.sub(r'[+\-][0-9]{2}:[0-9]{2}', '', input_time).replace('T', ' ')
        timestamp = int(datetime.strptime(cleaned_time, '%Y-%m-%d %H:%M:%S').timestamp())
        return timestamp
    except ValueError:
        print(f"Error: Failed to convert date '{input_time}'")
        return None

# 全局变量，表示时间间隔（单位：秒）
TIME_INTERVAL = 1800
# TIME_INTERVAL = 120

# 主函数
def process_log(log_file):
    # 全局 map，用于存储每个 mp3 文件及其访问记录
    mp3_access_map = {}

    # 读取日志文件
    with open(log_file, 'r', encoding='utf-8') as file:
        for line in file:
            #  提取目标文件
            if 'vvv=1' not in line:
                continue
            # 提取访问时间和路径
            access_time_match = re.search(r'\[(.*?)\]', line)
            if not access_time_match:
                continue
            access_time = access_time_match.group(1)  # 格式：2025-01-08T11:23:18+08:00
            mp3_path_match = re.search(r'\"(.*?)\"', line)
            if not mp3_path_match:
                continue
            mp3_path = mp3_path_match.group(1).split('?')[0]  # 去掉查询参数
            # 提取时间戳
            timestamp = convert_to_timestamp(access_time)
            if timestamp is None:
                continue

            # 提取文件名（例如 apple-v1587.mp3）
            mp3_filename = os.path.basename(mp3_path)

            # 提取文件所在的前3级目录
            mp3_dir = os.path.dirname(mp3_path)
            parts = mp3_dir.split('/')
            if len(parts) < 3:
                continue
            
            # print(f"*** Debug *** - parts#{parts}")
            # 找到 FILES 的索引
            try:
                files_index = parts.index('FILES')
            except ValueError:
                continue
            
            # 提取 FILES 之后的所有目录层级（除了最后一级，即文件对应的文件夹）
            if files_index + 1 < len(parts):  # 确保有足够的层级
                dir_parts = parts[files_index + 1:]  # 从 FILES 后的第一级到倒数第二级
                file_path = '/'.join(dir_parts)
            else:
                continue

            # 生成 key，作为存储访问记录的标识
            key = f"{file_path}/{mp3_filename}"            
            # print(f"*** Debug *** - key#{key}")

            # 如果该文件之前访问过，检查时间差是否大于 TIME_INTERVAL
            if key in mp3_access_map:
                last_access_time = mp3_access_map[key].split(',')[-1]
                last_access_timestamp = convert_to_timestamp(last_access_time)
                if last_access_timestamp is None:
                    continue
                # 判断访问时间差是否大于2分钟
                if timestamp - last_access_timestamp > TIME_INTERVAL:
                    mp3_access_map[key] += f",{access_time}"
            else:
                # 如果是第一次访问，初始化记录
                mp3_access_map[key] = access_time

    return mp3_access_map

# 用于嵌套结构的字典类型
def generate_statistics(mp3_access_map):
    def nested_dict():
        return defaultdict(nested_dict)

    frequency_map = nested_dict()

    # 计算每个文件的访问次数
    for key, value in mp3_access_map.items():
        times = value.split(',')  # 按逗号分割时间
        count = len(times)
        
        # 提取路径部分（避免路径重复）
        parts = key.split('/')
        file_name = parts[-1]
        path = parts[:-1]

        # 获取访问的目录层级
        current_dir = frequency_map
        for part in path:
            current_dir = current_dir[part]  # 递归进入子目录

        # 格式化时间，将时间转换为 YYYY-MM-DD HH:MM:SS 格式
        formatted_times = []
        for time in times:
            try:
                # 去掉时区部分并格式化
                cleaned_time = re.sub(r'[+\-][0-9]{2}:[0-9]{2}', '', time).replace('T', ' ')
                formatted_time = datetime.strptime(cleaned_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
                formatted_times.append(formatted_time)
            except ValueError:
                formatted_times.append(time)  # 如果格式化失败，保留原始时间

        # 存入文件数据
        current_dir[file_name] = (count, ' '.join(formatted_times))

    # 递归打印目录树
    def print_tree(current_dir, indent=""):
        for key, value in current_dir.items():
            if isinstance(value, dict):
                # 如果是子目录，打印目录名，并递归打印其内容
                print(f"{indent}- {key}:")
                print_tree(value, indent + "  ")
            else:
                # 否则打印文件信息
                count, times = value
                print(f"{indent}- {key} {count} {times}")

    # print_tree(frequency_map)

    # 递归写入文件
    def print_tree_to_file(current_dir, file, indent="", path_prefix="/#/FILES"):
        for key, value in current_dir.items():
            if isinstance(value, dict):
                # 如果是子目录，打印目录名，并递归打印其内容
                file.write(f"{indent}- {key}:\n")
                # 更新路径前缀以包含当前目录
                new_path_prefix = f"{path_prefix}/{key}"
                print_tree_to_file(value, file, indent + "  ", new_path_prefix)
            else:
                # 否则打印文件信息，并为文件添加超链接
                count, times = value
                # 提取文件夹名称（去掉 .mp3 后缀，并处理 -s1 或 -s2）
                if key.endswith(".mp3") or key.endswith(".mp4"):
                    # 构造文件的超链接
                    file_path = f"{path_prefix}/"
                    file.write(f"{indent}- <a href=\"{file_path}\">{key}</a> {count} [{times}]\n")
                else:
                    # 非 MP3/MP4 文件保持原格式
                    file.write(f"{indent}- {key} {count} [{times}]\n")

    # 获取当前时间
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 打开文件并写入
    # with open(r'E:\Developer\pix-ffmpig\py\analyze\chfs-metric.html', 'w', encoding='utf-8') as file:
    with open(r'H:\tmp\local\sum.html', 'w', encoding='utf-8') as file:
        # html前缀
        file.write("""<!DOCTYPE html>
    <html>
    <!-- TODO: 
      - 增量统计 
    -->
    <head>
        <title>Preview History</title>
    </head>
    <body>
    <H2>Update by {0}</H2>
    <pre>
    """.format(current_time))
        # 更新时间
        # file.write(f"================    {current_time}    ================\n")
        print_tree_to_file(frequency_map, file=file)

        # html后缀
        file.write("""</pre>
        </body>
        </html>
        """)

# 检查输入参数
if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <log_file_path>")
    sys.exit(1)

# 日志文件路径
log_file = sys.argv[1]

# 处理日志文件
mp3_access_map = process_log(log_file)

# 生成统计并排序输出
generate_statistics(mp3_access_map)

# run => python analyze.py "E:\Developer\nginx\nginx-1.22.1\logs\access_chfs.log"