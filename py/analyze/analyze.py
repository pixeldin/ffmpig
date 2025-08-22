import sys
import os
import re
import json
from datetime import datetime
from collections import defaultdict

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

# 主函数
def process_log(log_file):
    mp3_access_map = {}
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
            mp3_filename = os.path.basename(mp3_path).strip()
            if not mp3_filename:
                print(f"Warning: Empty filename in path '{mp3_path}'")
                continue
            mp3_dir = os.path.dirname(mp3_path)
            parts = [part.strip() for part in mp3_dir.split('/') if part.strip()]
            if len(parts) < 3:
                print(f"Warning: Invalid path structure in '{mp3_path}'")
                continue
            try:
                files_index = parts.index('FILES')
            except ValueError:
                print(f"Warning: 'FILES' not found in path '{mp3_path}'")
                continue
            if files_index + 1 < len(parts):
                dir_parts = parts[files_index + 1:]
                file_path = '/'.join(dir_parts)
            else:
                print(f"Warning: No directory after 'FILES' in path '{mp3_path}'")
                continue
            key = f"{file_path}/{mp3_filename}"
            if not key.strip() or ' ' in key.split('/')[-1]:
                print(f"Warning: Invalid key generated '{key}'")
                continue
            if key in mp3_access_map:
                last_access_time = mp3_access_map[key].split(',')[-1]
                last_access_timestamp = convert_to_timestamp(last_access_time)
                if last_access_timestamp is None:
                    continue
                if timestamp - last_access_timestamp > TIME_INTERVAL:
                    mp3_access_map[key] += f",{access_time}"
            else:
                mp3_access_map[key] = access_time
    return mp3_access_map

# 用于嵌套结构的字典类型
def generate_statistics(mp3_access_map):
    def nested_dict():
        return defaultdict(nested_dict)

    frequency_map = nested_dict()

    # 计算每个文件的访问次数
    for key, value in mp3_access_map.items():
        times = value.split(',')
        count = len(times)
        parts = [part.strip() for part in key.split('/') if part.strip()]
        if not parts:
            print(f"Warning: Empty parts in key '{key}'")
            continue
        file_name = parts[-1]
        path = parts[:-1]
        if not file_name:
            print(f"Warning: Empty file name in key '{key}'")
            continue
        current_dir = frequency_map
        for part in path:
            if not part or part.isspace():
                print(f"Warning: Empty or invalid path part '{part}' in key '{key}'")
                continue
            current_dir = current_dir[part]
        formatted_times = []
        for time in times:
            try:
                cleaned_time = re.sub(r'[+\-][0-9]{2}:[0-9]{2}', '', time).replace('T', ' ')
                formatted_time = datetime.strptime(cleaned_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
                formatted_times.append(formatted_time)
            except ValueError:
                formatted_times.append(time)
        if not isinstance(current_dir['files'], list):
            current_dir['files'] = []
        current_dir['files'].append({'name': file_name, 'count': count, 'times': formatted_times})

    # 调试：打印 frequency_map
    print("frequency_map:", json.dumps(frequency_map, indent=2, default=lambda x: dict(x)))

    # 获取当前时间
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # HTML 内容模板
    html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>文件访问日志</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .tree-node > ul {{ display: none; }}
    .tree-node.active > ul {{ display: block; }}
    .tree-node > span {{ cursor: pointer; }}
    .file-item {{ transition: background-color 0.2s; }}
    .file-item:hover {{ background-color: #f1f5f9; }}
  </style>
</head>
<body class="bg-gray-100 font-sans">
  <div class="container mx-auto p-6">
    <h1 class="text-3xl font-bold text-gray-800 mb-6">文件访问日志 (更新时间: {0})</h1>
    <div class="bg-white shadow-lg rounded-lg p-6">
      <ul id="tree" class="space-y-2">
      </ul>
    </div>
  </div>

  <script>
    const logData = {1};

    function renderTree(data, parentElement, path = '') {{
      for (const [dir, contents] of Object.entries(data)) {{
        const currentPath = path ? `${{path}}/${{dir}}` : dir;
        const dirLi = document.createElement('li');
        dirLi.className = 'tree-node';
        dirLi.innerHTML = `
          <span class="flex items-center text-gray-700 font-semibold hover:text-blue-600">
            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
            </svg>
            ${{dir}}
          </span>
          <ul class="pl-6 space-y-2"></ul>
        `;
        parentElement.appendChild(dirLi);
        const ul = dirLi.querySelector('ul');

        if (dir === 'files') {{
          contents.forEach(file => {{
            const fileLi = document.createElement('li');
            fileLi.className = 'file-item pl-4 py-1 rounded';
            fileLi.innerHTML = `
              <div class="flex justify-between">
                <a href="/#/FILES/${{path}}/" target="_blank" class="text-blue-600 hover:underline">${{file.name}}</a>
                <span class="text-gray-500 text-sm">
                  访问次数: ${{file.count}} | 访问时间: ${{file.times.join(', ')}}
                </span>
              </div>
            `;
            ul.appendChild(fileLi);
          }});
        }} else {{
          renderTree(contents, ul, currentPath);
        }}
      }}
    }}

    const tree = document.getElementById('tree');
    renderTree(logData, tree);

    // 一次性绑定点击事件
    document.querySelectorAll('.tree-node > span').forEach(span => {{
      span.addEventListener('click', () => {{
        const li = span.parentElement;
        li.classList.toggle('active');
        const svg = span.querySelector('svg');
        svg.classList.toggle('rotate-90');
        console.log('Clicked directory:', span.textContent.trim());
      }});
    }});
  </script>
</body>
</html>
"""

    # 转换 frequency_map 为 logData 格式
    def convert_to_log_data(frequency_map):
        def convert_dict(d):
            result = {}
            for key, value in d.items():
                if not key or key.isspace():
                    print(f"Warning: Skipping invalid key '{key}'")
                    continue
                if isinstance(value, list):
                    result[key] = value
                elif isinstance(value, dict):
                    result[key] = convert_dict(value)
                else:
                    print(f"Warning: Unexpected value type for key '{key}': {type(value)}")
            return result
        return convert_dict(frequency_map)

    log_data_json = json.dumps(convert_to_log_data(frequency_map), ensure_ascii=False, default=lambda x: dict(x))

    # 调试：打印 html_content 占位符
    print("html_content placeholders:", re.findall(r'\{[^}]*\}', html_content))

    # 写入 HTML 文件
    output_paths = [
        r'H:\tmp\local\sum.html',
        r'I:\files\sum.html'
    ]

    for path in output_paths:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            print(f"目录不存在: {directory}")
            continue
        with open(path, 'w', encoding='utf-8') as file:
            file.write(html_content.format(current_time, log_data_json))

# 检查输入参数
if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <log_file_path>")
    sys.exit(1)

log_file = sys.argv[1]
mp3_access_map = process_log(log_file)
generate_statistics(mp3_access_map)