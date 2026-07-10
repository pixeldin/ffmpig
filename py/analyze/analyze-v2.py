import sys
import os
import re
import json
import shutil
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# 辅助函数：将日期时间字符串转为时间戳
def convert_to_timestamp(input_time):
    try:
        cleaned_time = re.sub(r'[+\-][0-9]{2}:[0-9]{2}', '', input_time).replace('T', ' ')
        timestamp = int(datetime.strptime(cleaned_time, '%Y-%m-%d %H:%M:%S').timestamp())
        return timestamp
    except ValueError:
        print(f"Error: Failed to convert date '{input_time}'")
        return None

# 全局时间间隔（单位：秒）
TIME_INTERVAL = 1800

# 扫描 CHFS 共享目录，获取所有文件
def scan_chfs_directory(root_path, base_name='FILES'):
    """
    扫描 CHFS 共享目录，建立完整文件树
    返回: {
        'file_path/file.mp4': {
            'exists': True,
            'preview': 'pc-file.png',  # 预览图文件名
            'full_path': 'E:/path/to/file.mp4'
        }
    }
    """
    file_map = {}
    preview_map = {}  # 存储预览图: {dir_path: [preview_files]}
    
    print(f"开始扫描目录: {root_path}")
    
    if not os.path.exists(root_path):
        print(f"错误: 目录不存在 '{root_path}'")
        return file_map
    
    # 第一遍：收集所有预览图
    for root, dirs, files in os.walk(root_path):
        # 过滤掉 wind-sum 目录
        if 'wind-sum' in root.split(os.sep):
            continue
            
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                rel_dir = os.path.relpath(root, root_path)
                if rel_dir not in preview_map:
                    preview_map[rel_dir] = []
                preview_map[rel_dir].append(file)
    
    # 第二遍：收集所有文件并关联预览图
    for root, dirs, files in os.walk(root_path):
        rel_dir = os.path.relpath(root, root_path)
        
        # 过滤掉 wind-sum 目录
        if 'wind-sum' in rel_dir.split(os.sep):
            continue
        
        for file in files:
            full_path = os.path.join(root, file)
            
            # 构建相对路径 (相对于 root_path)
            if rel_dir == '.':
                file_key = file
            else:
                file_key = f"{rel_dir}/{file}".replace('\\', '/')
            
            # 过滤掉特定文件
            if file.lower() in ['desktop.ini'] or file.lower().endswith('mk.txt') or file.lower().endswith('.srt'):
                continue
            
            # 查找对应的预览图 (同目录下的任意图片)
            preview_file = None
            is_image = file.lower().endswith(('.png', '.jpg', '.jpeg'))
            
            # 跳过图片文件，不添加到文件列表中
            if is_image:
                continue
            
            if rel_dir in preview_map and len(preview_map[rel_dir]) > 0:
                # 选择目录中的第一张图片作为预览
                preview_file = preview_map[rel_dir][0]
            
            file_map[file_key] = {
                'exists': True,
                'preview': preview_file,
                'full_path': full_path,
                'size': os.path.getsize(full_path),
                'is_image': False  # 已经过滤掉图片，这里都是非图片文件
            }
    
    print(f"扫描完成，共找到 {len(file_map)} 个文件")
    return file_map

# 解析访问日志
def process_log(log_file):
    """解析日志文件，返回访问记录"""
    mp3_access_map = {}
    
    if not os.path.exists(log_file):
        print(f"警告: 日志文件不存在 '{log_file}'")
        return mp3_access_map
    
    print(f"开始解析日志: {log_file}")
    
    with open(log_file, 'r', encoding='utf-8') as file:
        for line in file:
            if 'vvv=1' not in line:
                continue
            
            access_time_match = re.search(r'\[(.*?)\]', line)
            if not access_time_match:
                continue
            access_time = access_time_match.group(1)
            
            mp3_path_match = re.search(r'\"(.*?)\"', line)
            if not mp3_path_match:
                continue
            mp3_path = mp3_path_match.group(1).split('?')[0].strip()
            
            timestamp = convert_to_timestamp(access_time)
            if timestamp is None:
                continue
            
            # 从路径中提取 FILES 之后的部分
            if '/FILES/' not in mp3_path:
                continue
            
            # 提取 FILES 之后的完整路径
            files_part = mp3_path.split('/FILES/')[1]
            
            # 过滤掉特定文件和目录
            if 'wind-sum' in files_part or files_part.lower().endswith('desktop.ini') or files_part.lower().endswith('.mk.txt'):
                continue
            
            # 构建 key (相对于 FILES 的路径) - 规范化路径
            key = files_part.replace('\\', '/').strip()
            
            if key in mp3_access_map:
                last_access_time = mp3_access_map[key].split(',')[-1]
                last_access_timestamp = convert_to_timestamp(last_access_time)
                if last_access_timestamp is None:
                    continue
                if timestamp - last_access_timestamp > TIME_INTERVAL:
                    mp3_access_map[key] += f",{access_time}"
            else:
                mp3_access_map[key] = access_time
    
    print(f"日志解析完成，共 {len(mp3_access_map)} 个文件有访问记录")
    return mp3_access_map

# 合并文件扫描结果和访问日志
def merge_data(file_map, access_map):
    """
    合并文件系统扫描和访问日志数据
    返回统一的数据结构
    """
    merged = {}
    
    # 先添加所有扫描到的文件
    for file_key, file_info in file_map.items():
        merged[file_key] = {
            'exists': True,
            'preview': file_info['preview'],
            'size': file_info['size'],
            'count': 0,
            'times': [],
            'is_image': file_info.get('is_image', False)
        }
    
    # 再添加访问记录
    for file_key, access_times in access_map.items():
        times = access_times.split(',')
        
        if file_key in merged:
            merged[file_key]['count'] = len(times)
            merged[file_key]['times'] = times
        else:
            # 日志中有但文件系统中没有的文件（可能已删除）
            merged[file_key] = {
                'exists': False,
                'preview': None,
                'size': 0,
                'count': len(times),
                'times': times
            }
    
    return merged

# 生成统计数据文件并部署前端页面
REPORT_OUTPUT_DIRS = [
    Path(r'H:\tmp\local\wind-sum'),
    Path(r'I:\files\wind-sum')
]
FRONTEND_DIR = Path(__file__).resolve().parent / 'report_frontend'
FRONTEND_FILES = ['sum-v2.html', 'style.css', 'app.js']


def build_report_payload(merged_data, chfs_base_url='http://192.168.28.67:9527'):
    """生成前端消费的结构化报表数据。"""
    def nested_dict():
        return defaultdict(nested_dict)

    frequency_map = nested_dict()

    for key, value in merged_data.items():
        parts = [part.strip() for part in key.split('/') if part.strip()]
        if not parts:
            continue

        file_name = parts[-1]
        path_parts = parts[:-1]
        current_dir = frequency_map
        for part in path_parts:
            if not part or part.isspace():
                continue
            current_dir = current_dir[part]

        formatted_times = []
        for access_time in value.get('times', []):
            try:
                cleaned_time = re.sub(r'[+\-][0-9]{2}:[0-9]{2}', '', access_time).replace('T', ' ')
                formatted_time = datetime.strptime(cleaned_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
                formatted_times.append(formatted_time)
            except ValueError:
                formatted_times.append(access_time)

        preview_url = None
        if value.get('preview'):
            preview_path = '/'.join(path_parts) if path_parts else ''
            if preview_path:
                preview_url = f"{chfs_base_url}/chfs/shared/FILES/{preview_path}/{value['preview']}"
            else:
                preview_url = f"{chfs_base_url}/chfs/shared/FILES/{value['preview']}"

        if not isinstance(current_dir['files'], list):
            current_dir['files'] = []

        existing_file = None
        for item in current_dir['files']:
            if item['name'] == file_name:
                existing_file = item
                break

        if existing_file:
            existing_file['times'] = sorted(list(set(existing_file['times'] + formatted_times)))
            existing_file['count'] = len(existing_file['times'])
            if not existing_file.get('preview') and preview_url:
                existing_file['preview'] = preview_url
            if value.get('exists'):
                existing_file['exists'] = True
            if value.get('size', 0) > existing_file.get('size', 0):
                existing_file['size'] = value.get('size', 0)
        else:
            current_dir['files'].append({
                'name': file_name,
                'count': len(formatted_times),
                'times': formatted_times,
                'exists': value.get('exists', False),
                'preview': preview_url,
                'size': value.get('size', 0),
                'is_image': value.get('is_image', False)
            })

    def convert_to_log_data(node):
        result = {}
        for key, value in node.items():
            if not key or key.isspace():
                continue
            if isinstance(value, list):
                result[key] = value
            elif isinstance(value, dict):
                result[key] = convert_to_log_data(value)
        return result

    visited_count = sum(1 for value in merged_data.values() if value.get('count', 0) > 0)
    return {
        'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'chfsBaseUrl': chfs_base_url,
        'summary': {
            'total': len(merged_data),
            'visited': visited_count,
            'unvisited': len(merged_data) - visited_count,
            'withPreview': sum(1 for value in merged_data.values() if value.get('preview'))
        },
        'logData': convert_to_log_data(frequency_map)
    }


def ensure_frontend_ready():
    missing = [name for name in FRONTEND_FILES if not (FRONTEND_DIR / name).exists()]
    if missing:
        raise FileNotFoundError(f"前端文件缺失: {', '.join(missing)}")


def write_report_files(payload, output_dirs=None):
    """写入 data.json/data.js，并复制独立前端文件到报表目录。"""
    ensure_frontend_ready()
    output_dirs = output_dirs or REPORT_OUTPUT_DIRS
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    payload_js = f"window.__REPORT_DATA__ = {payload_json};\n"

    for output_dir in output_dirs:
        if not output_dir.exists():
            print(f"目录不存在: {output_dir}")
            continue

        (output_dir / 'data.json').write_text(payload_json, encoding='utf-8')
        (output_dir / 'data.js').write_text(payload_js, encoding='utf-8')

        for file_name in FRONTEND_FILES:
            shutil.copy2(FRONTEND_DIR / file_name, output_dir / file_name)

        print(f"报表数据已生成: {output_dir / 'data.json'}")
        print(f"前端页面已部署: {output_dir / 'sum-v2.html'}")


def generate_statistics(merged_data, chfs_base_url='http://192.168.28.67:9527'):
    """保持旧调用名，生成报表数据并部署前端。"""
    payload = build_report_payload(merged_data, chfs_base_url)
    write_report_files(payload)


# 主函数
def main():
    if len(sys.argv) < 3:
        print(f"用法: {sys.argv[0]} <log_file_path> <chfs_root_directory> [chfs_base_url]")
        print(f"示例: {sys.argv[0]} access.log F:/FILES http://192.168.28.67:9527")
        sys.exit(1)
    
    log_file = sys.argv[1]
    chfs_root = sys.argv[2]
    chfs_base_url = sys.argv[3] if len(sys.argv) > 3 else 'http://192.168.28.67:9527'
    
    print("=" * 60)
    print("文件访问日志分析工具 (增强版 v2)")
    print("=" * 60)
    print(f"日志文件: {log_file}")
    print(f"CHFS 根目录: {chfs_root}")
    print(f"CHFS 基础 URL: {chfs_base_url}")
    print("=" * 60)
    
    # 步骤 1: 扫描文件系统
    print("\n[1/4] 扫描 CHFS 共享目录...")
    file_map = scan_chfs_directory(chfs_root)
    
    # 步骤 2: 解析访问日志
    print("\n[2/4] 解析访问日志...")
    access_map = process_log(log_file)
    
    # 步骤 3: 合并数据
    print("\n[3/4] 合并数据...")
    merged_data = merge_data(file_map, access_map)
    print(f"合并完成，共 {len(merged_data)} 个文件")
    print(f"  - 已访问: {sum(1 for v in merged_data.values() if v['count'] > 0)}")
    print(f"  - 未访问: {sum(1 for v in merged_data.values() if v['count'] == 0)}")
    print(f"  - 有预览图: {sum(1 for v in merged_data.values() if v['preview'])}")
    
    # 步骤 4: 生成 HTML
    print("\n[4/4] 生成 HTML 报告...")
    generate_statistics(merged_data, chfs_base_url)
    
    print("\n" + "#" * 60)
    print("完成！")
    print("#" * 60)

    print("\n")

if __name__ == '__main__':
    main()

