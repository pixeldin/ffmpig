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
    # print("frequency_map:", json.dumps(frequency_map, indent=2, default=lambda x: dict(x)))

    # 获取当前时间
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # HTML 内容模板
    html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>文件访问日志</title>
  <!-- <script src="https://cdn.tailwindcss.com"></script> -->
  <script src="js/tailwindcss.js"></script>
  <style>
    .tree-node > ul {{ display: none; }}
    .tree-node.active > ul {{ display: block; }}
    .tree-node > span {{ cursor: pointer; }}
    .file-item {{ transition: background-color 0.2s; }}
    .file-item:hover {{ background-color: #f1f5f9; }}
    .highlight {{ background-color: #fef08a; }}
    .hidden-node {{ display: none; }}
    .btn-active {{ background-color: #3b82f6; color: white; }}
    /* 移动端适配 */
    @media (max-width: 640px) {{
      .container {{ padding: 0.75rem; }}
      .toolbar-row {{ flex-direction: column; align-items: stretch; gap: 0.5rem; }}
      .toolbar-group {{ width: 100%; }}
      .toolbar-group select, .toolbar-group input[type="date"] {{ flex: 1; min-width: 0; }}
      #customRange {{ flex-wrap: wrap; }}
      #customRange input[type="date"] {{ flex: 1; min-width: 100px; }}
      /* 列表视图：卡片模式 */
      #listView table {{ display: none; }}
      #listView .mobile-cards {{ display: flex; flex-direction: column; gap: 0.5rem; }}
      /* 树形视图增加触摸间距 */
      .tree-node > span {{ padding: 0.5rem 0; }}
      .file-item {{ padding: 0.5rem 0.25rem; }}
      .file-item .flex {{ flex-direction: column; gap: 0.25rem; }}
    }}
    @media (min-width: 641px) {{
      #listView .mobile-cards {{ display: none; }}
    }}
  </style>
</head>
<body class="bg-gray-100 font-sans">
  <div class="container mx-auto p-6">
    <h1 class="text-xl sm:text-3xl font-bold text-gray-800 mb-4">文件访问日志 (更新时间: {0})</h1>

    <!-- 工具栏 -->
    <div class="bg-white shadow rounded-lg p-4 mb-4 space-y-3">
      <!-- 搜索 -->
      <div class="flex items-center gap-3">
        <input id="searchInput" type="text" placeholder="搜索文件名或路径..."
          class="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
        <button id="clearSearch" class="text-sm text-gray-500 hover:text-red-500">清除</button>
      </div>
      <!-- 视图 + 排序 + 时间 -->
      <div class="flex flex-wrap items-center gap-3 text-sm toolbar-row">
        <div class="flex items-center gap-1 toolbar-group">
          <span class="text-gray-600 shrink-0">视图:</span>
          <button id="btnTree" class="px-3 py-1 rounded border border-gray-300 btn-active" data-view="tree">树形</button>
          <button id="btnList" class="px-3 py-1 rounded border border-gray-300" data-view="list">列表</button>
        </div>
        <div class="flex items-center gap-1 toolbar-group">
          <span class="text-gray-600 shrink-0">排序:</span>
          <select id="sortSelect" class="border border-gray-300 rounded px-2 py-1">
            <option value="default">默认</option>
            <option value="count-desc">次数 ↓</option>
            <option value="count-asc">次数 ↑</option>
            <option value="time-desc">最近访问 ↓</option>
            <option value="time-asc">最近访问 ↑</option>
          </select>
        </div>
        <div class="flex items-center gap-1 toolbar-group">
          <span class="text-gray-600 shrink-0">时间:</span>
          <select id="timeFilter" class="border border-gray-300 rounded px-2 py-1">
            <option value="all">全部</option>
            <option value="1w">最近一周</option>
            <option value="1m">最近一月</option>
            <option value="3m">最近三月</option>
            <option value="custom">自定义</option>
          </select>
        </div>
        <div id="customRange" class="hidden flex items-center gap-1 toolbar-group">
          <input id="dateFrom" type="date" class="border border-gray-300 rounded px-2 py-1" />
          <span class="text-gray-400">~</span>
          <input id="dateTo" type="date" class="border border-gray-300 rounded px-2 py-1" />
          <button id="applyRange" class="px-2 py-1 bg-blue-500 text-white rounded text-xs shrink-0">应用</button>
        </div>
        <span id="resultCount" class="text-gray-400 sm:ml-auto"></span>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="bg-white shadow-lg rounded-lg p-3 sm:p-6">
      <ul id="tree" class="space-y-2"></ul>
      <div id="listView" class="hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b text-left text-gray-600">
              <th class="py-2 px-2">文件名</th>
              <th class="py-2 px-2">路径</th>
              <th class="py-2 px-2 text-center">次数</th>
              <th class="py-2 px-2">访问时间</th>
            </tr>
          </thead>
          <tbody id="listBody"></tbody>
        </table>
        <div class="mobile-cards" id="mobileCards"></div>
      </div>
    </div>
  </div>

  <script>
    const logData = {1};

    // === 扁平化 logData 为文件列表 ===
    function flattenData(data, path = '') {{
      let files = [];
      for (const [key, val] of Object.entries(data)) {{
        if (key === 'files') {{
          val.forEach(f => {{
            const lastTime = f.times[f.times.length - 1];
            files.push({{ name: f.name, path: path, count: f.count, times: f.times, lastTime }});
          }});
        }} else {{
          files = files.concat(flattenData(val, path ? path + '/' + key : key));
        }}
      }}
      return files;
    }}
    const allFiles = flattenData(logData);

    // === 时间筛选 ===
    function getTimeRange() {{
      const v = document.getElementById('timeFilter').value;
      const now = new Date();
      if (v === 'all') return null;
      if (v === '1w') return new Date(now - 7 * 86400000);
      if (v === '1m') return new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
      if (v === '3m') return new Date(now.getFullYear(), now.getMonth() - 3, now.getDate());
      if (v === 'custom') {{
        const from = document.getElementById('dateFrom').value;
        return from ? new Date(from) : null;
      }}
      return null;
    }}
    function getTimeEnd() {{
      const v = document.getElementById('timeFilter').value;
      if (v === 'custom') {{
        const to = document.getElementById('dateTo').value;
        return to ? new Date(to + 'T23:59:59') : null;
      }}
      return null;
    }}
    function filterByTime(files) {{
      const rangeStart = getTimeRange();
      const rangeEnd = getTimeEnd();
      if (!rangeStart && !rangeEnd) return files;
      return files.filter(f => {{
        return f.times.some(t => {{
          const d = new Date(t);
          if (rangeStart && d < rangeStart) return false;
          if (rangeEnd && d > rangeEnd) return false;
          return true;
        }});
      }});
    }}

    // === 搜索过滤 ===
    function filterBySearch(files, keyword) {{
      if (!keyword) return files;
      const kw = keyword.toLowerCase();
      return files.filter(f => f.name.toLowerCase().includes(kw) || f.path.toLowerCase().includes(kw));
    }}

    // === 排序 ===
    function sortFiles(files) {{
      const v = document.getElementById('sortSelect').value;
      const sorted = [...files];
      if (v === 'count-desc') sorted.sort((a, b) => b.count - a.count);
      else if (v === 'count-asc') sorted.sort((a, b) => a.count - b.count);
      else if (v === 'time-desc') sorted.sort((a, b) => new Date(b.lastTime) - new Date(a.lastTime));
      else if (v === 'time-asc') sorted.sort((a, b) => new Date(a.lastTime) - new Date(b.lastTime));
      return sorted;
    }}

    // === 列表视图渲染 ===
    function renderList() {{
      const keyword = document.getElementById('searchInput').value.trim();
      let files = filterBySearch(allFiles, keyword);
      files = filterByTime(files);
      files = sortFiles(files);
      const tbody = document.getElementById('listBody');
      const mobileCards = document.getElementById('mobileCards');
      tbody.innerHTML = '';
      mobileCards.innerHTML = '';
      files.forEach(f => {{
        // 桌面端表格行
        const tr = document.createElement('tr');
        tr.className = 'border-b hover:bg-gray-50';
        tr.innerHTML = `
          <td class="py-2 px-2"><a href="/#/FILES/${{f.path}}/" target="_blank" class="text-blue-600 hover:underline">${{f.name}}</a></td>
          <td class="py-2 px-2 text-gray-500">${{f.path}}</td>
          <td class="py-2 px-2 text-center">${{f.count}}</td>
          <td class="py-2 px-2 text-gray-500 text-xs">${{f.times.join(', ')}}</td>
        `;
        tbody.appendChild(tr);
        // 移动端卡片
        const card = document.createElement('div');
        card.className = 'border rounded-lg p-3 bg-gray-50';
        const timeTags = f.times.map(t => `<span class="inline-block bg-gray-200 text-gray-600 rounded px-1.5 py-0.5">${{t}}</span>`).join('');
        card.innerHTML = `
          <div class="font-medium"><a href="/#/FILES/${{f.path}}/" target="_blank" class="text-blue-600 hover:underline">${{f.name}}</a></div>
          <div class="text-xs text-gray-400 mt-1 break-all">${{f.path}}</div>
          <div class="flex items-center mt-2 text-xs text-gray-500">
            <span class="shrink-0">次数: ${{f.count}}</span>
          </div>
          <div class="flex flex-wrap gap-1 mt-1.5 text-xs">${{timeTags}}</div>
        `;
        mobileCards.appendChild(card);
      }});
      document.getElementById('resultCount').textContent = `共 ${{files.length}} 个文件`;
    }}

    // === 树形视图渲染 ===
    function renderTree(data, parentElement, path = '') {{
      for (const [dir, contents] of Object.entries(data)) {{
        if (dir === 'files') {{
          contents.forEach(file => {{
            const fileLi = document.createElement('li');
            fileLi.className = 'file-item pl-4 py-1 rounded';
            fileLi.setAttribute('data-name', file.name.toLowerCase());
            fileLi.setAttribute('data-path', path.toLowerCase());
            fileLi.setAttribute('data-times', file.times.join(','));
            fileLi.innerHTML = `
              <div class="flex justify-between">
                <a href="/#/FILES/${{path}}/" target="_blank" class="text-blue-600 hover:underline">${{file.name}}</a>
                <span class="text-gray-500 text-sm">
                  次数: ${{file.count}} | 时间: ${{file.times.join(', ')}}
                </span>
              </div>
            `;
            parentElement.appendChild(fileLi);
          }});
        }} else {{
          const currentPath = path ? `${{path}}/${{dir}}` : dir;
          const dirLi = document.createElement('li');
          dirLi.className = 'tree-node';
          dirLi.innerHTML = `
            <span class="flex items-center text-gray-700 font-semibold hover:text-blue-600">
              <svg class="w-4 h-4 mr-2 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
              </svg>
              ${{dir}}
            </span>
            <ul class="pl-6 space-y-2"></ul>
          `;
          parentElement.appendChild(dirLi);
          const ul = dirLi.querySelector('ul');
          renderTree(contents, ul, currentPath);
        }}
      }}
    }}

    function initTree() {{
      const tree = document.getElementById('tree');
      tree.innerHTML = '';
      renderTree(logData, tree);
      document.querySelectorAll('.tree-node > span').forEach(span => {{
        span.addEventListener('click', () => {{
          const li = span.parentElement;
          li.classList.toggle('active');
          span.querySelector('svg').classList.toggle('rotate-90');
        }});
      }});
    }}

    // === 树形视图搜索 + 时间过滤 ===
    function filterTree() {{
      const keyword = document.getElementById('searchInput').value.trim().toLowerCase();
      const rangeStart = getTimeRange();
      const rangeEnd = getTimeEnd();
      // 先重置所有节点
      document.querySelectorAll('#tree .file-item').forEach(el => {{
        el.classList.remove('hidden-node', 'highlight');
      }});
      document.querySelectorAll('#tree .tree-node').forEach(el => {{
        el.classList.remove('hidden-node');
        el.classList.remove('active');
        el.querySelector('svg').classList.remove('rotate-90');
      }});

      const hasFilter = keyword || rangeStart || rangeEnd;
      if (!hasFilter) {{
        const count = document.querySelectorAll('#tree .file-item').length;
        document.getElementById('resultCount').textContent = `共 ${{count}} 个文件`;
        return;
      }}

      let visibleCount = 0;
      // 过滤文件项
      document.querySelectorAll('#tree .file-item').forEach(el => {{
        const name = el.getAttribute('data-name');
        const path = el.getAttribute('data-path');
        const times = el.getAttribute('data-times').split(',');
        let matchKeyword = !keyword || name.includes(keyword) || path.includes(keyword);
        let matchTime = true;
        if (rangeStart || rangeEnd) {{
          matchTime = times.some(t => {{
            const d = new Date(t);
            if (rangeStart && d < rangeStart) return false;
            if (rangeEnd && d > rangeEnd) return false;
            return true;
          }});
        }}
        if (matchKeyword && matchTime) {{
          if (keyword) el.classList.add('highlight');
          visibleCount++;
        }} else {{
          el.classList.add('hidden-node');
        }}
      }});

      // 隐藏没有可见子文件的目录节点，展开有可见子文件的
      function processNode(node) {{
        const childFiles = node.querySelectorAll(':scope > ul > .file-item:not(.hidden-node)');
        const childDirs = node.querySelectorAll(':scope > ul > .tree-node');
        let hasVisible = childFiles.length > 0;
        childDirs.forEach(d => {{
          if (processNode(d)) hasVisible = true;
        }});
        if (!hasVisible) {{
          node.classList.add('hidden-node');
        }} else {{
          node.classList.add('active');
          node.querySelector('svg').classList.add('rotate-90');
        }}
        return hasVisible;
      }}
      document.querySelectorAll('#tree > .tree-node').forEach(n => processNode(n));
      document.getElementById('resultCount').textContent = `共 ${{visibleCount}} 个文件`;
    }}

    // === 视图切换 ===
    let currentView = 'tree';
    function switchView(view) {{
      currentView = view;
      document.getElementById('btnTree').classList.toggle('btn-active', view === 'tree');
      document.getElementById('btnList').classList.toggle('btn-active', view === 'list');
      document.getElementById('tree').classList.toggle('hidden', view !== 'tree');
      document.getElementById('listView').classList.toggle('hidden', view !== 'list');
      refresh();
    }}

    function refresh() {{
      if (currentView === 'list') renderList();
      else filterTree();
    }}

    // === 事件绑定 ===
    document.getElementById('btnTree').addEventListener('click', () => switchView('tree'));
    document.getElementById('btnList').addEventListener('click', () => switchView('list'));
    document.getElementById('searchInput').addEventListener('input', refresh);
    document.getElementById('clearSearch').addEventListener('click', () => {{
      document.getElementById('searchInput').value = '';
      refresh();
    }});
    document.getElementById('sortSelect').addEventListener('change', refresh);
    document.getElementById('timeFilter').addEventListener('change', () => {{
      document.getElementById('customRange').classList.toggle('hidden',
        document.getElementById('timeFilter').value !== 'custom');
      if (document.getElementById('timeFilter').value !== 'custom') refresh();
    }});
    document.getElementById('applyRange').addEventListener('click', refresh);

    // === 初始化 ===
    initTree();
    refresh();
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
    # print("html_content placeholders:", re.findall(r'\{[^}]*\}', html_content))

    # 写入 HTML 文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(script_dir, '..', '..')
    output_paths = [
        os.path.join(project_root, 'demo', 'wind-sum', 'sum.html'),
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
