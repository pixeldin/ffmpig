# 报表文件最近更新时间排序 Spec

## 1. 背景

当前 `sum-v2.html` 报表页面主要围绕访问日志统计展示文件信息，包括文件名、访问次数、访问时间、文件大小和预览图。文件大小、预览图等信息来自 `analyze-v2.py` 的 CHFS 文件系统扫描。

现有文件扫描核心结构:

```python
file_map[file_key] = {
    "exists": True,
    "preview": preview_file,
    "full_path": full_path,
    "size": os.path.getsize(full_path),
    "is_image": False
}
```

页面目前可以按访问次数、最近访问时间等维度排序，但无法按“文件本身最近更新时间”排序。

## 2. 目标

为报表增加文件最近更新时间字段，并在前端页面支持按文件更新时间排序。

目标能力:

- 后端扫描文件时记录文件最近修改时间。
- 报表数据 `data.json` / `data.js` 输出文件更新时间。
- 前端列表/树形视图显示文件更新时间。
- 排序下拉增加“最近更新”和“最早更新”。
- `CHFS_ROOT` 不存在时仍能降级运行，更新时间为空并排序到最后。

## 3. 非目标

本次不做:

- 不新增数据库表持久化文件元数据。
- 不改变访问日志增量同步逻辑。
- 不改变 `file_visit` / `raw_log_event` 表结构。
- 不实现按文件更新时间的时间范围筛选。
- 不实现文件变更监听。

## 4. 字段设计

建议后端输出两个字段:

```json
{
  "modifiedTs": 1783699200,
  "modifiedTime": "2026-07-10 23:18:05"
}
```

字段说明:

- `modifiedTs`: Unix timestamp，数字类型，供前端排序使用。
- `modifiedTime`: 可读时间字符串，供页面展示使用。

命名建议使用前端已有风格的 camelCase。后端内部可以使用 snake_case，但输出 payload 时应转换为 camelCase。

缺失文件或无法扫描文件系统时:

```json
{
  "modifiedTs": null,
  "modifiedTime": null
}
```

## 5. 后端改动范围

### 5.1 scan_chfs_directory()

位置:

```text
py/analyze/analyze-v2.py
```

当前扫描文件时使用:

```python
os.path.getsize(full_path)
```

建议改为:

```python
stat = os.stat(full_path)
size = stat.st_size
modified_ts = int(stat.st_mtime)
modified_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
```

然后写入:

```python
file_map[file_key] = {
    "exists": True,
    "preview": preview_file,
    "full_path": full_path,
    "size": size,
    "modified_ts": modified_ts,
    "modified_time": modified_time,
    "is_image": False
}
```

注意:

- 使用 `os.stat()` 一次拿到 size 和 mtime，避免重复访问文件系统。
- 如果 `os.stat()` 因文件被删除或权限问题失败，应跳过该文件或记录 warning，不应中断整个扫描。

### 5.2 merge_data()

位置:

```text
py/analyze/analyze-v2.py
```

扫描到的文件应带上:

```python
"modified_ts": file_info.get("modified_ts"),
"modified_time": file_info.get("modified_time")
```

日志中存在但文件系统不存在的文件应填:

```python
"modified_ts": None,
"modified_time": None
```

这样可以保证前端字段稳定存在。

### 5.3 build_report_payload()

位置:

```text
py/analyze/analyze-v2.py
```

输出给前端时建议转换为:

```python
{
    "name": file_name,
    "count": len(formatted_times),
    "times": formatted_times,
    "exists": value.get("exists", False),
    "preview": preview_url,
    "size": value.get("size", 0),
    "modifiedTs": value.get("modified_ts"),
    "modifiedTime": value.get("modified_time"),
    "is_image": value.get("is_image", False)
}
```

如果同名文件合并，更新时间应采用较新的文件更新时间:

```text
existing.modifiedTs = max(existing.modifiedTs, incoming.modifiedTs)
```

同时同步对应的 `modifiedTime`。

## 6. report_builder.py 影响

`report_builder.py` 当前复用 `analyze-v2.py` 的:

- `scan_chfs_directory()`
- `merge_data()`
- `generate_statistics()`

因此只要 `analyze-v2.py` 的字段链路补齐，从 SQLite 生成报表也会自动带上文件更新时间。

当 `CHFS_ROOT` 不存在时:

- `scan_chfs_directory()` 返回空 `file_map`。
- `merge_data()` 只会合并数据库访问记录。
- `modifiedTs` / `modifiedTime` 应为空。
- 页面仍可显示和排序，只是更新时间为空的文件排在最后。

## 7. 前端改动范围

### 7.1 flattenData()

位置:

```text
py/analyze/report_frontend/app.js
```

确保文件对象保留:

```javascript
modifiedTs: file.modifiedTs ?? null,
modifiedTime: file.modifiedTime ?? null
```

### 7.2 排序选项

位置:

```text
py/analyze/report_frontend/sum-v2.html
```

在 `sortSelect` 增加:

```html
<option value="modified-desc">最近更新</option>
<option value="modified-asc">最早更新</option>
```

### 7.3 排序逻辑

位置:

```text
py/analyze/report_frontend/app.js
```

新增排序分支:

```javascript
if (sort === "modified-desc") {
  files = files.sort((a, b) => nullLastCompare(b.modifiedTs, a.modifiedTs));
}

if (sort === "modified-asc") {
  files = files.sort((a, b) => nullLastCompare(a.modifiedTs, b.modifiedTs));
}
```

建议实现一个空值排最后的比较函数:

```javascript
function nullLastCompare(a, b) {
  const aMissing = a === null || a === undefined || a === "";
  const bMissing = b === null || b === undefined || b === "";
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  return Number(a) - Number(b);
}
```

### 7.4 页面展示

位置:

```text
py/analyze/report_frontend/app.js
```

当前 meta 显示文件缺失和大小:

```javascript
meta.textContent = [file.exists === false ? "文件缺失" : "", formatSize(file.size)]
  .filter(Boolean)
  .join(" / ");
```

建议改为:

```javascript
meta.textContent = [
  file.exists === false ? "文件缺失" : "",
  formatSize(file.size),
  file.modifiedTime ? `更新 ${file.modifiedTime}` : ""
].filter(Boolean).join(" / ");
```

## 8. 页面布局建议

新增“文件更新时间”后，页面中会同时出现两个时间概念:

- 访问时间: 用户访问该文件的时间，来自 Nginx 日志 / SQLite。
- 更新时间: 文件本身最后修改时间，来自 CHFS 文件系统扫描。

建议 UI 文案避免混淆:

### 8.1 排序文案

排序下拉建议改为:

```text
默认
访问次数降序
访问次数升序
最近访问
最早访问
最近更新
最早更新
```

### 8.2 时间筛选文案

当前时间筛选实际按“访问时间”过滤，建议将标签从:

```text
时间
```

改为:

```text
访问时间
```

这样不会和文件更新时间混淆。

### 8.3 文件行展示

文件 meta 建议保持紧凑:

```text
12.3 MB / 更新 2026-07-10 23:18:05
```

缺失文件:

```text
文件缺失
```

缺失文件没有 `modifiedTime` 时不显示“更新”字段。

## 9. 验收标准

### 9.1 CHFS_ROOT 存在

输入:

```text
I:\files 存在，且包含若干文件。
```

期望:

- `data.json` 中每个存在的文件包含 `modifiedTs` 和 `modifiedTime`。
- 页面文件行显示更新时间。
- “最近更新”排序把较新的文件排在前面。
- “最早更新”排序把较旧的文件排在前面。

### 9.2 CHFS_ROOT 不存在

输入:

```text
I:\files 不存在。
```

期望:

- 报表生成不失败。
- 访问记录仍显示。
- `modifiedTs` / `modifiedTime` 为 `null`。
- 按更新时间排序时，这些文件排在最后。

### 9.3 文件扫描中途文件被删除

输入:

```text
扫描过程中某个文件被删除。
```

期望:

- 扫描不中断。
- 该文件可跳过或标记为缺失。
- 其他文件正常进入报表。

## 10. 后续扩展

如果后续希望在 `CHFS_ROOT` 不存在时仍保留上次扫描到的文件更新时间，可以新增数据库表:

```sql
CREATE TABLE file_metadata (
  file_key TEXT PRIMARY KEY,
  size INTEGER,
  modified_ts INTEGER,
  modified_time TEXT,
  preview TEXT,
  exists INTEGER NOT NULL,
  scanned_at TEXT NOT NULL
);
```

该扩展不属于本次改动范围。

