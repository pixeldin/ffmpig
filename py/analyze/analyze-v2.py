import sys
import os
import re
import json
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

# 生成统计数据和 HTML
def generate_statistics(merged_data, chfs_base_url='http://192.168.28.67:9527'):
    """生成嵌套的目录结构和 HTML"""
    def nested_dict():
        return defaultdict(nested_dict)
    
    frequency_map = nested_dict()
    
    # 构建目录树结构
    for key, value in merged_data.items():
        parts = [part.strip() for part in key.split('/') if part.strip()]
        if not parts:
            continue
        
        file_name = parts[-1]
        path = parts[:-1]
        
        current_dir = frequency_map
        for part in path:
            if not part or part.isspace():
                continue
            current_dir = current_dir[part]
        
        # 格式化时间
        formatted_times = []
        for time in value['times']:
            try:
                cleaned_time = re.sub(r'[+\-][0-9]{2}:[0-9]{2}', '', time).replace('T', ' ')
                formatted_time = datetime.strptime(cleaned_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
                formatted_times.append(formatted_time)
            except ValueError:
                formatted_times.append(time)
        
        # 构建预览图 URL (使用直接访问路径,不用 # 路由)
        preview_url = None
        if value['preview']:
            preview_path = '/'.join(path) if path else ''
            if preview_path:
                preview_url = f"{chfs_base_url}/chfs/shared/FILES/{preview_path}/{value['preview']}"
            else:
                preview_url = f"{chfs_base_url}/chfs/shared/FILES/{value['preview']}"
        
        if not isinstance(current_dir['files'], list):
            current_dir['files'] = []
        
        # 检查是否已存在同名文件，如果存在则合并访问记录
        existing_file = None
        for f in current_dir['files']:
            if f['name'] == file_name:
                existing_file = f
                break
        
        if existing_file:
            # 合并访问记录
            existing_file['count'] += value['count']
            existing_file['times'].extend(formatted_times)
            # 去重并排序时间
            existing_file['times'] = sorted(list(set(existing_file['times'])))
            existing_file['count'] = len(existing_file['times'])
            # 更新其他字段（保留已有的非空值）
            if not existing_file.get('preview') and preview_url:
                existing_file['preview'] = preview_url
            if value['exists']:
                existing_file['exists'] = True
            if value['size'] > existing_file.get('size', 0):
                existing_file['size'] = value['size']
        else:
            # 添加新文件
            current_dir['files'].append({
                'name': file_name,
                'count': value['count'],
                'times': formatted_times,
                'exists': value['exists'],
                'preview': preview_url,
                'size': value['size'],
                'is_image': value.get('is_image', False)
            })
    
    # 获取当前时间
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # HTML 内容模板（增强版）
    html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>文件访问日志 (增强版)</title>
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
    .unvisited {{ opacity: 0.5; }}
    .preview-thumb {{ max-width: 120px; max-height: 80px; object-fit: cover; border-radius: 4px; cursor: pointer; }}
    .preview-thumb:hover {{ opacity: 0.8; }}
    /* 大图预览模态框 */
    .modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.9); }}
    .modal.show {{ display: flex; align-items: center; justify-content: center; padding: 20px; }}
    .modal-content {{ max-width: 90%; max-height: 90%; object-fit: contain; }}
    .modal-close {{ position: absolute; top: 20px; right: 40px; color: #fff; font-size: 40px; font-weight: bold; cursor: pointer; user-select: none; }}
    .modal-close:hover {{ color: #ccc; }}
    /* 视频播放器模态框 */
    .video-modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.95); }}
    .video-modal.show {{ display: flex; align-items: center; justify-content: center; padding: 20px; }}
    .video-container {{ width: 100%; max-width: 1200px; max-height: 90vh; }}
    .video-player {{ width: 100%; height: auto; max-height: 90vh; }}
    /* 移动端优化 */
    @media (max-width: 640px) {{
      .modal.show, .video-modal.show {{ padding: 10px; }}
      .modal-content {{ max-width: 95%; max-height: 85%; }}
      .modal-close {{ top: 10px; right: 15px; font-size: 30px; }}
      .video-container {{ max-height: 85vh; }}
      .video-player {{ max-height: 85vh; }}
      .preview-thumb {{ max-width: 80px; max-height: 60px; }}
    }}
    /* 视频预览 */
    .video-modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.95); }}
    .video-modal.show {{ display: flex; align-items: center; justify-content: center; }}
    .video-container {{ width: 90%; max-width: 1200px; }}
    .video-player {{ width: 100%; max-height: 80vh; }}
    @media (max-width: 640px) {{
      .container {{ padding: 0.75rem; }}
      .toolbar-row {{ flex-direction: column; align-items: stretch; gap: 0.5rem; }}
      .toolbar-group {{ width: 100%; }}
      .toolbar-group select, .toolbar-group input[type="date"] {{ flex: 1; min-width: 0; }}
      #customRange {{ flex-wrap: wrap; }}
      #customRange input[type="date"] {{ flex: 1; min-width: 100px; }}
      #listView table {{ display: none; }}
      #listView .mobile-cards {{ display: flex; flex-direction: column; gap: 0.5rem; }}
      .tree-node > span {{ padding: 0.5rem 0; }}
      .file-item {{ padding: 0.5rem 0.25rem; }}
      .file-item .flex {{ flex-direction: column; gap: 0.25rem; }}
      /* 移动端按钮优化 */
      button {{ font-size: 0.75rem; padding: 0.375rem 0.75rem; }}
      .preview-thumb {{ margin-left: 0; margin-top: 0.5rem; }}
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
      <!-- 视图 + 排序 + 时间 + 过滤 -->
      <div class="flex flex-wrap items-center gap-3 text-sm toolbar-row">
        <div class="flex items-center gap-1 toolbar-group">
          <span class="text-gray-600 shrink-0">视图:</span>
          <button id="btnTree" class="px-3 py-1 rounded border border-gray-300 btn-active" data-view="tree">树形</button>
          <button id="btnList" class="px-3 py-1 rounded border border-gray-300" data-view="list">列表</button>
        </div>
        <div class="flex items-center gap-1 toolbar-group">
          <span class="text-gray-600 shrink-0">显示:</span>
          <select id="visitFilter" class="border border-gray-300 rounded px-2 py-1">
            <option value="all">全部文件</option>
            <option value="visited">仅已访问</option>
            <option value="unvisited">仅未访问</option>
          </select>
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
              <th class="py-2 px-2">预览</th>
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
    
    <!-- 图片预览模态框 -->
    <div id="imageModal" class="modal" onclick="closeModal()">
      <span class="modal-close">&times;</span>
      <img id="modalImage" class="modal-content" onclick="event.stopPropagation()" alt="预览图片">
    </div>
    
    <!-- 视频播放器模态框 -->
    <div id="videoModal" class="video-modal" onclick="closeVideoModal()">
      <span class="modal-close">&times;</span>
      <div class="video-container" onclick="event.stopPropagation()">
        <video id="videoPlayer" class="video-player" controls autoplay>
          <source id="videoSource" src="" type="video/mp4">
          您的浏览器不支持视频播放。
        </video>
      </div>
    </div>
  </div>

  <script>
    const logData = {1};
    const chfsBaseUrl = '{2}';
    
    // 图片预览功能
    function showImage(src) {{
      document.getElementById('modalImage').src = src;
      document.getElementById('imageModal').classList.add('show');
      document.body.style.overflow = 'hidden'; // 防止背景滚动
    }}
    
    function closeModal() {{
      document.getElementById('imageModal').classList.remove('show');
      document.body.style.overflow = ''; // 恢复滚动
    }}
    
    // 视频播放功能
    function showVideo(src, event) {{
      if (event) {{
        event.preventDefault();
        event.stopPropagation();
      }}
      const videoPlayer = document.getElementById('videoPlayer');
      const videoSource = document.getElementById('videoSource');
      videoSource.src = src;
      videoPlayer.load();
      document.getElementById('videoModal').classList.add('show');
      document.body.style.overflow = 'hidden'; // 防止背景滚动
    }}
    
    function closeVideoModal() {{
      const videoPlayer = document.getElementById('videoPlayer');
      videoPlayer.pause();
      document.getElementById('videoModal').classList.remove('show');
      document.body.style.overflow = ''; // 恢复滚动
    }}
    
    // 复制链接到剪贴板
    function copyLink(url, button) {{
      const linkWithVvv = url + '&vvv=1';
      navigator.clipboard.writeText(linkWithVvv).then(() => {{
        const originalText = button.textContent;
        button.textContent = '已复制';
        button.classList.add('bg-green-500');
        button.classList.remove('bg-blue-500', 'hover:bg-blue-600');
        setTimeout(() => {{
          button.textContent = originalText;
          button.classList.remove('bg-green-500');
          button.classList.add('bg-blue-500', 'hover:bg-blue-600');
        }}, 1500);
      }}).catch(err => {{
        alert('复制失败: ' + err);
      }});
    }}
    
    // ESC 键关闭模态框
    document.addEventListener('keydown', (e) => {{
      if (e.key === 'Escape') {{
        closeModal();
        closeVideoModal();
      }}
    }});

    // === 扁平化 logData 为文件列表 ===
    function flattenData(data, path = '') {{
      let files = [];
      for (const [key, val] of Object.entries(data)) {{
        if (key === 'files') {{
          val.forEach(f => {{
            const lastTime = f.times.length > 0 ? f.times[f.times.length - 1] : null;
            files.push({{ 
              name: f.name, 
              path: path, 
              count: f.count, 
              times: f.times, 
              lastTime: lastTime,
              exists: f.exists,
              preview: f.preview,
              size: f.size,
              is_image: f.is_image || false
            }});
          }});
        }} else {{
          files = files.concat(flattenData(val, path ? path + '/' + key : key));
        }}
      }}
      return files;
    }}
    const allFiles = flattenData(logData);

    // === 访问过滤 ===
    function filterByVisit(files) {{
      const v = document.getElementById('visitFilter').value;
      // 过滤掉图片文件
      files = files.filter(f => !f.is_image && !f.name.match(/\\.(png|jpg|jpeg)$/i));
      if (v === 'all') return files;
      if (v === 'visited') return files.filter(f => f.count > 0);
      if (v === 'unvisited') return files.filter(f => f.count === 0);
      return files;
    }}

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
        if (f.times.length === 0) return true; // 未访问的文件总是显示
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
      else if (v === 'time-desc') sorted.sort((a, b) => {{
        if (!a.lastTime) return 1;
        if (!b.lastTime) return -1;
        return new Date(b.lastTime) - new Date(a.lastTime);
      }});
      else if (v === 'time-asc') sorted.sort((a, b) => {{
        if (!a.lastTime) return 1;
        if (!b.lastTime) return -1;
        return new Date(a.lastTime) - new Date(b.lastTime);
      }});
      return sorted;
    }}

    // === 格式化文件大小 ===
    function formatSize(bytes) {{
      if (bytes === 0) return '0 B';
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
    }}

    // === 列表视图渲染 ===
    function renderList() {{
      const keyword = document.getElementById('searchInput').value.trim();
      let files = filterBySearch(allFiles, keyword);
      files = filterByVisit(files);
      files = filterByTime(files);
      files = sortFiles(files);
      
      // 统计信息
      const totalFiles = files.length;
      const visitedFiles = files.filter(f => f.count > 0).length;
      const unvisitedFiles = files.filter(f => f.count === 0).length;
      const uniquePaths = new Set(files.map(f => f.path)).size;
      
      const tbody = document.getElementById('listBody');
      const mobileCards = document.getElementById('mobileCards');
      tbody.innerHTML = '';
      mobileCards.innerHTML = '';
      files.forEach(f => {{
        const visitClass = f.count === 0 ? 'unvisited' : '';
        // 显示预览图
        const previewHtml = f.preview 
          ? `<img src="${{f.preview}}" class="preview-thumb" alt="预览" onclick="showImage('${{f.preview}}')" onerror="this.style.display='none'">` 
          : '';
        const timesHtml = f.times.length > 0 ? f.times.join(', ') : '<span class="text-gray-400">未访问</span>';
        
        // 构建文件真实地址 - 视频文件加上 ?v=1 参数
        const isVideo = f.name.match(/\\.(mp4|mkv|avi|mov|wmv|flv|webm)$/i);
        const videoUrl = `${{chfsBaseUrl}}/chfs/shared/FILES/${{f.path ? f.path + '/' : ''}}${{f.name}}${{isVideo ? '?v=1' : ''}}`;
        const fileUrl = videoUrl;
        const onclickAttr = isVideo ? `onclick="showVideo('${{videoUrl}}', event); return false;"` : '';
        
        // 为视频文件添加复制按钮
        const copyButtonHtml = isVideo 
          ? `<button onclick="copyLink('` + videoUrl + `', this)" class="px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors whitespace-nowrap shrink-0">选中复制</button>` 
          : '';
        
        // 桌面端表格行
        const tr = document.createElement('tr');
        tr.className = `border-b hover:bg-gray-50 ${{visitClass}}`;
        tr.innerHTML = `
          <td class="py-2 px-2">${{previewHtml || '<span class="text-gray-400 text-xs">-</span>'}}</td>
          <td class="py-2 px-2">
            <div class="flex items-center gap-2 flex-wrap">
              <a href="${{fileUrl}}" ${{onclickAttr}} target="_blank" class="text-blue-600 hover:underline break-all">${{f.name}}</a>
              ${{copyButtonHtml}}
            </div>
          </td>
          <td class="py-2 px-2 text-gray-500">${{f.path}}</td>
          <td class="py-2 px-2 text-center">${{f.count}}</td>
          <td class="py-2 px-2 text-gray-500 text-xs">${{timesHtml}}</td>
        `;
        tbody.appendChild(tr);
        
        // 移动端卡片
        const card = document.createElement('div');
        card.className = `border rounded-lg p-3 bg-gray-50 ${{visitClass}}`;
        const timeTags = f.times.length > 0 
          ? f.times.map(t => `<span class="inline-block bg-gray-200 text-gray-600 rounded px-1.5 py-0.5 text-xs">${{t}}</span>`).join('')
          : '<span class="text-gray-400 text-xs">未访问</span>';
        const cardPreview = previewHtml ? `<div class="mb-2">${{previewHtml}}</div>` : '';
        card.innerHTML = `
          ${{cardPreview}}
          <div class="flex flex-col gap-2">
            <div class="font-medium break-all"><a href="${{fileUrl}}" ${{onclickAttr}} target="_blank" class="text-blue-600 hover:underline">${{f.name}}</a></div>
            ${{copyButtonHtml ? `<div>${{copyButtonHtml}}</div>` : ''}}
          </div>
          <div class="text-xs text-gray-400 mt-2 break-all">${{f.path}}</div>
          <div class="flex items-center mt-2 text-xs text-gray-500">
            <span class="shrink-0">次数: ${{f.count}}</span>
          </div>
          <div class="flex flex-wrap gap-1 mt-1.5">${{timeTags}}</div>
        `;
        mobileCards.appendChild(card);
      }});
      document.getElementById('resultCount').textContent = `共 ${{totalFiles}} 个文件 | ${{uniquePaths}} 个目录 | 已访问: ${{visitedFiles}} | 未访问: ${{unvisitedFiles}}`;
    }}

    // === 树形视图渲染 ===
    function renderTree(data, parentElement, path = '') {{
      for (const [dir, contents] of Object.entries(data)) {{
        if (dir === 'files') {{
          contents.forEach(file => {{
            const visitClass = file.count === 0 ? 'unvisited' : '';
            // 显示预览图
            const previewHtml = file.preview 
              ? `<img src="${{file.preview}}" class="preview-thumb ml-2" alt="预览" onclick="showImage('${{file.preview}}')" onerror="this.style.display='none'">` 
              : '';
            const timesHtml = file.times.length > 0 
              ? `次数: ${{file.count}} | 时间: ${{file.times.join(', ')}}` 
              : '未访问';
            
            // 构建文件真实地址 - 视频文件加上 ?v=1 参数
            const isVideo = file.name.match(/\\.(mp4|mkv|avi|mov|wmv|flv|webm)$/i);
            const videoUrl = `${{chfsBaseUrl}}/chfs/shared/FILES/${{path ? path + '/' : ''}}${{file.name}}${{isVideo ? '?v=1' : ''}}`;
            const fileUrl = videoUrl;
            const onclickAttr = isVideo ? `onclick="showVideo('${{videoUrl}}', event); return false;"` : '';
            
            // 为视频文件添加复制按钮
            const copyButtonHtml = isVideo 
              ? `<button onclick="copyLink('` + videoUrl + `', this)" class="ml-2 px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors whitespace-nowrap">选中复制</button>` 
              : '';
            
            const fileLi = document.createElement('li');
            fileLi.className = `file-item pl-4 py-1 rounded ${{visitClass}}`;
            fileLi.setAttribute('data-name', file.name.toLowerCase());
            fileLi.setAttribute('data-path', path.toLowerCase());
            fileLi.setAttribute('data-times', file.times.join(','));
            fileLi.setAttribute('data-count', file.count);
            fileLi.innerHTML = `
              <div class="flex justify-between items-center flex-wrap gap-2">
                <div class="flex items-center gap-2 flex-wrap">
                  <a href="${{fileUrl}}" ${{onclickAttr}} target="_blank" class="text-blue-600 hover:underline break-all">${{file.name}}</a>
                  ${{copyButtonHtml}}
                  ${{previewHtml}}
                </div>
                <span class="text-gray-500 text-sm whitespace-nowrap">
                  ${{timesHtml}}
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

    // === 树形视图搜索 + 时间过滤 + 访问过滤 ===
    function filterTree() {{
      const keyword = document.getElementById('searchInput').value.trim().toLowerCase();
      const rangeStart = getTimeRange();
      const rangeEnd = getTimeEnd();
      const visitFilter = document.getElementById('visitFilter').value;
      
      // 先重置所有节点
      document.querySelectorAll('#tree .file-item').forEach(el => {{
        el.classList.remove('hidden-node', 'highlight');
      }});
      document.querySelectorAll('#tree .tree-node').forEach(el => {{
        el.classList.remove('hidden-node');
        el.classList.remove('active');
        el.querySelector('svg').classList.remove('rotate-90');
      }});

      const hasFilter = keyword || rangeStart || rangeEnd || visitFilter !== 'all';
      if (!hasFilter) {{
        const allFileItems = document.querySelectorAll('#tree .file-item');
        const totalFiles = allFileItems.length;
        const visitedFiles = Array.from(allFileItems).filter(el => parseInt(el.getAttribute('data-count')) > 0).length;
        const unvisitedFiles = totalFiles - visitedFiles;
        const uniquePaths = new Set(Array.from(allFileItems).map(el => el.getAttribute('data-path'))).size;
        document.getElementById('resultCount').textContent = `共 ${{totalFiles}} 个文件 | ${{uniquePaths}} 个目录 | 已访问: ${{visitedFiles}} | 未访问: ${{unvisitedFiles}}`;
        return;
      }}

      let visibleCount = 0;
      let visitedCount = 0;
      let unvisitedCount = 0;
      const visiblePaths = new Set();
      
      // 过滤文件项
      document.querySelectorAll('#tree .file-item').forEach(el => {{
        const name = el.getAttribute('data-name');
        const path = el.getAttribute('data-path');
        const times = el.getAttribute('data-times').split(',').filter(t => t);
        const count = parseInt(el.getAttribute('data-count'));
        
        let matchKeyword = !keyword || name.includes(keyword) || path.includes(keyword);
        
        let matchVisit = true;
        if (visitFilter === 'visited') matchVisit = count > 0;
        else if (visitFilter === 'unvisited') matchVisit = count === 0;
        
        let matchTime = true;
        if ((rangeStart || rangeEnd) && times.length > 0) {{
          matchTime = times.some(t => {{
            const d = new Date(t);
            if (rangeStart && d < rangeStart) return false;
            if (rangeEnd && d > rangeEnd) return false;
            return true;
          }});
        }}
        
        if (matchKeyword && matchTime && matchVisit) {{
          if (keyword) el.classList.add('highlight');
          visibleCount++;
          if (count > 0) visitedCount++;
          else unvisitedCount++;
          if (path) visiblePaths.add(path);
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
      document.getElementById('resultCount').textContent = `共 ${{visibleCount}} 个文件 | ${{visiblePaths.size}} 个目录 | 已访问: ${{visitedCount}} | 未访问: ${{unvisitedCount}}`;
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
    document.getElementById('visitFilter').addEventListener('change', refresh);
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
                    continue
                if isinstance(value, list):
                    result[key] = value
                elif isinstance(value, dict):
                    result[key] = convert_dict(value)
            return result
        return convert_dict(frequency_map)
    
    log_data_json = json.dumps(convert_to_log_data(frequency_map), ensure_ascii=False, default=lambda x: dict(x))
    
    # 写入 HTML 文件
    output_paths = [
        r'H:\tmp\local\wind-sum\sum-v2.html',
        r'I:\files\wind-sum\sum-v2.html'
    ]
    
    for path in output_paths:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            print(f"目录不存在: {directory}")
            continue
        with open(path, 'w', encoding='utf-8') as file:
            file.write(html_content.format(current_time, log_data_json, chfs_base_url))
        print(f"HTML 文件已生成: {path}")


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
