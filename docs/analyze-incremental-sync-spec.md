# CHFS 访问日志增量同步后端改造 Spec

## 1. 背景

当前 `py/analyze/analyze-v2.py` 的日志分析链路仍以 Nginx 访问日志为实时数据源。`py/analyze/alz.bat` 周期性从 `access_chfs.log` 中筛选 `vvv=1` 记录，再调用 `analyze-v2.py` 全量解析日志、扫描 CHFS 文件目录，并生成前端报表数据。

现有链路:

```text
Nginx access_chfs.log
  -> alz.bat 全量过滤 vvv=1
  -> analyze-v2.py 全量解析日志
  -> 扫描 CHFS 文件目录
  -> 生成 data.json / data.js
  -> report_frontend 页面渲染
```

问题:

- 每轮都全量读取日志，日志增长后处理成本持续上升。
- 历史访问依赖 Nginx 日志文件，日志清理或轮转后历史不可恢复。
- 统计逻辑和日志读取状态没有持久化，难以支持幂等重跑。
- 后续引入更复杂筛选、历史查询或多来源合并时，缺少稳定的数据层。

## 2. 目标

第二阶段改造目标是引入 SQLite 和增量同步脚本，将访问事件先稳定落库，再由报表生成逻辑从数据库聚合数据。

目标链路:

```text
Nginx access_chfs.log
  -> ingest_log.py 增量读取新增日志
  -> SQLite 幂等保存访问事件
  -> report builder 从 SQLite + CHFS 文件扫描生成 data.json / data.js
  -> report_frontend 页面渲染
```

本阶段必须满足:

- 支持首次全量初始化历史日志。
- 支持后续按日志 offset 增量同步。
- 重复执行不会重复统计访问记录。
- 支持日志截断、清空、轮转后的恢复读取。
- 保持前端数据接口稳定，前端仍只消费 `data.json` / `data.js`。

## 3. 非目标

本阶段不做:

- 不引入 MySQL/PostgreSQL 等外部服务。
- 不改变前端页面的数据消费方式。
- 不替换 Nginx/CHFS 部署方式。
- 不实现复杂用户认证、远程管理后台或多用户权限。
- 不要求实时监听文件变化，仍可以由 `alz.bat` 或计划任务周期性调用。

## 4. 架构拆分

推荐拆分为三个后端职责:

```text
py/analyze/
  ingest_log.py              # 日志增量入库
  analyze-v2.py              # 过渡期报表生成入口
  report_store.py            # SQLite 连接、建表、读写封装
  report_builder.py          # 从数据库和文件扫描结果生成 report payload
  report_frontend/           # 已拆出的前端静态页面
```

### 4.1 ingest_log.py

职责:

- 接收 Nginx 日志路径和 SQLite 数据库路径。
- 读取 `log_state` 中保存的 offset。
- 从 offset 继续读取新增日志行。
- 过滤 `vvv=1`。
- 解析访问时间、状态码、访问路径、文件 key。
- 生成稳定 `event_key`。
- 幂等写入 `raw_log_event`。
- 根据 30 分钟规则写入 `file_visit`。
- 更新 `log_state`。

建议命令:

```bash
python py/analyze/ingest_log.py init E:/Developer/nginx/nginx-1.22.1/logs/access_chfs.log py/analyze/visit_stats.db
python py/analyze/ingest_log.py tail E:/Developer/nginx/nginx-1.22.1/logs/access_chfs.log py/analyze/visit_stats.db
```

### 4.2 report_store.py

职责:

- 统一管理 SQLite schema。
- 提供事务封装。
- 提供插入原始日志事件、插入有效访问记录、读取同步状态、保存同步状态等 API。
- 让 `ingest_log.py` 和报表生成代码不直接散落 SQL。

推荐函数:

```python
def connect(db_path): ...
def ensure_schema(conn): ...
def get_log_state(conn, log_path): ...
def save_log_state(conn, state): ...
def insert_raw_event(conn, event): ...
def get_last_visit_ts(conn, file_key): ...
def insert_file_visit(conn, visit): ...
def query_visit_summary(conn): ...
```

### 4.3 report_builder.py

职责:

- 扫描 CHFS 共享目录，保留当前 `scan_chfs_directory()` 的能力。
- 从 SQLite 查询有效访问记录。
- 合并文件存在状态、文件大小、预览图、访问次数、访问时间。
- 生成和当前前端兼容的 payload:

```json
{
  "updatedAt": "2026-07-10 12:00:00",
  "chfsBaseUrl": "http://192.168.28.67:9527",
  "summary": {
    "total": 100,
    "visited": 20,
    "unvisited": 80,
    "withPreview": 60
  },
  "logData": {}
}
```

### 4.4 analyze-v2.py 过渡策略

短期内可以保留 `analyze-v2.py` 作为报表生成入口:

- 第一阶段已经拆出前端静态文件。
- 第二阶段可以先新增 `ingest_log.py`，不立刻删除 `analyze-v2.py` 的日志解析能力。
- 等 SQLite 数据源验证稳定后，再把 `analyze-v2.py` 内部数据源从日志文件切换到 SQLite，或新增 `build_report.py` 替代它。

## 5. 数据库设计

数据库使用 SQLite，默认文件:

```text
py/analyze/visit_stats.db
```

### 5.1 log_state

保存每个日志文件的增量读取状态。

```sql
CREATE TABLE IF NOT EXISTS log_state (
  log_path TEXT PRIMARY KEY,
  offset INTEGER NOT NULL DEFAULT 0,
  file_size INTEGER NOT NULL DEFAULT 0,
  fingerprint TEXT,
  updated_at TEXT NOT NULL
);
```

字段说明:

- `log_path`: 日志文件绝对路径。
- `offset`: 上次成功处理到的字节位置。
- `file_size`: 上次处理时的日志大小。
- `fingerprint`: 日志文件指纹，可由文件头部/尾部 hash、mtime、size 组合生成。
- `updated_at`: 状态更新时间。

### 5.2 raw_log_event

保存解析后的原始访问事件。该表是幂等的第一道防线。

```sql
CREATE TABLE IF NOT EXISTS raw_log_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT NOT NULL UNIQUE,
  file_key TEXT NOT NULL,
  access_time TEXT NOT NULL,
  access_ts INTEGER NOT NULL,
  status_code INTEGER,
  raw_path TEXT NOT NULL,
  raw_line TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_log_event_file_key
  ON raw_log_event(file_key);

CREATE INDEX IF NOT EXISTS idx_raw_log_event_access_ts
  ON raw_log_event(access_ts);
```

字段说明:

- `event_key`: 单条日志事件唯一键。
- `file_key`: `FILES/` 后面的相对文件路径，例如 `E-sysTemp/body/demo/a.mp3`。
- `access_time`: 原始访问时间字符串。
- `access_ts`: 转换后的 Unix 时间戳。
- `status_code`: Nginx HTTP 状态码，例如 `200`、`206`、`499`。
- `raw_path`: 原始 URL path，去掉或保留 query 均可，但策略必须稳定。
- `raw_line`: 原始日志行，便于排查解析问题。

`event_key` 推荐生成方式:

```text
sha256(access_time + "|" + status_code + "|" + raw_path + "|" + raw_line)
```

写入方式:

```sql
INSERT OR IGNORE INTO raw_log_event (...)
```

### 5.3 file_visit

保存统计意义上的访问记录。它和原始日志不同，同一文件 30 分钟内连续访问只算一次。

```sql
CREATE TABLE IF NOT EXISTS file_visit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_key TEXT NOT NULL,
  access_time TEXT NOT NULL,
  access_ts INTEGER NOT NULL,
  raw_event_key TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  FOREIGN KEY(raw_event_key) REFERENCES raw_log_event(event_key)
);

CREATE INDEX IF NOT EXISTS idx_file_visit_file_key
  ON file_visit(file_key);

CREATE INDEX IF NOT EXISTS idx_file_visit_access_ts
  ON file_visit(access_ts);
```

30 分钟去重逻辑:

```text
查询 file_visit 中同一 file_key 最近一次 access_ts。
如果不存在，插入。
如果 new_access_ts - last_access_ts > 1800，插入。
否则不插入 file_visit，但 raw_log_event 仍保留。
```

不要仅使用 `floor(access_ts / 1800)` 作为唯一桶，因为它不能严格表达“距离上一次超过 30 分钟”的规则。

## 6. 增量同步流程

### 6.1 init 模式

用途: 第一次启用数据库时导入历史日志。

流程:

```text
1. ensure_schema()
2. offset = 0
3. 从头读取 access_chfs.log
4. 逐行解析并写入 raw_log_event / file_visit
5. 保存 log_state.offset = 当前文件末尾位置
6. 提交事务
```

`init` 必须可重复执行。重复执行时，`raw_log_event.event_key UNIQUE` 和 `file_visit.raw_event_key UNIQUE` 保证不会重复入库。

### 6.2 tail 模式

用途: 周期任务中处理新增日志。

流程:

```text
1. ensure_schema()
2. 读取 log_state
3. 获取当前日志 size 和 fingerprint
4. 如果当前 size < state.offset，则认为日志被截断或轮转，offset = 0
5. seek(offset)
6. 读取新增日志行
7. 逐行解析并幂等入库
8. 保存新的 offset、file_size、fingerprint
9. 提交事务
```

### 6.3 失败恢复

推荐事务策略:

- 一次 `tail` 运行使用单个事务。
- 只有所有新增行处理完成后才更新 `log_state.offset`。
- 如果中途失败，事务回滚，下次从旧 offset 重新读取。
- 由于 `raw_log_event` 使用唯一键，重复读取不会重复统计。

如果日志文件特别大，可以按批次提交，但每个批次必须在“事件写入”和“offset 更新”之间保持一致。

## 7. 日志解析规则

输入示例:

```text
[2025-01-08T11:23:18+08:00] 206 "/chfs/shared/FILES/E-sysTemp/body/demo/a.mp3?v=1&vvv=1"
```

解析规则:

- 只处理包含 `vvv=1` 的行。
- 从 `[]` 提取 `access_time`。
- 从状态码字段提取 `status_code`。
- 从双引号中提取 URL。
- query 中是否有额外参数不影响 `file_key`。
- `file_key` 取 `/FILES/` 后面的路径，去掉 query。
- 过滤 `desktop.ini`、`.mk.txt`、`.srt`、图片文件等规则应与当前 `analyze-v2.py` 保持一致。

解析失败的行:

- 不应中断整个同步。
- 建议打印 warning。
- 可后续增加 `parse_error_log` 表保存失败行。

## 8. alz.bat 调整建议

当前 `alz.bat` 的日志处理是:

```bat
type access_chfs.log | findstr "vvv=1" > tar_chfs.log
python.exe analyze-v2.py tar_chfs.log I:\files http://192.168.28.67:9527
```

第二阶段后建议改为:

```bat
python.exe "E:\Developer\pix-ffmpig\py\analyze\ingest_log.py" tail ^
  "E:\Developer\nginx\nginx-1.22.1\logs\access_chfs.log" ^
  "E:\Developer\pix-ffmpig\py\analyze\visit_stats.db"

python.exe "E:\Developer\pix-ffmpig\py\analyze\build_report.py" ^
  "E:\Developer\pix-ffmpig\py\analyze\visit_stats.db" ^
  "I:\files" ^
  "http://192.168.28.67:9527"
```

过渡期也可以先保留 `analyze-v2.py` 生成报表:

```bat
python.exe ingest_log.py tail access_chfs.log visit_stats.db
python.exe analyze-v2.py --from-db visit_stats.db I:\files http://192.168.28.67:9527
```

## 9. 代码分段计划

建议按小步落地，避免一次改动破坏现有报表。

### Step 1: 新增 SQLite 基础层

新增:

```text
py/analyze/report_store.py
```

实现:

- 连接数据库。
- 建表。
- 读写 `log_state`。
- 插入 `raw_log_event`。
- 插入 `file_visit`。

验收:

- 单独运行建库。
- 重复建库不报错。
- 重复插入同一 `event_key` 不产生重复行。

### Step 2: 新增 ingest_log.py

新增:

```text
py/analyze/ingest_log.py
```

实现:

- `init` / `tail` CLI。
- 日志增量读取。
- 行解析。
- 幂等入库。
- offset 保存。

验收:

- `init` 导入现有日志。
- 重复 `init` 行数不变。
- `tail` 只处理追加的新行。
- offset 回退或日志截断时不重复统计。

### Step 3: 报表读取 SQLite

新增或重构:

```text
py/analyze/report_builder.py
```

实现:

- 从 `file_visit` 聚合每个 `file_key` 的访问次数和时间列表。
- 复用 CHFS 文件扫描。
- 输出当前前端兼容 payload。

验收:

- 与旧全量日志统计结果抽样一致。
- 前端页面无需改动即可渲染。

### Step 4: 调整 alz.bat

修改周期任务:

- 去掉 `type | findstr` 全量过滤。
- 先运行 `ingest_log.py tail`。
- 再运行报表生成脚本。

验收:

- 连续运行多轮，数据库记录不重复增长。
- 新增访问记录后下一轮可以出现在报表中。

## 10. 测试用例

### 10.1 幂等

输入:

```text
同一份 access_chfs.log 连续执行 init 两次
```

期望:

- `raw_log_event` 行数不变。
- `file_visit` 行数不变。
- `log_state.offset` 保持在文件末尾。

### 10.2 增量

输入:

```text
先执行 tail。
向 access_chfs.log 追加一条 vvv=1 记录。
再次执行 tail。
```

期望:

- 只新增一条 `raw_log_event`。
- 是否新增 `file_visit` 取决于 30 分钟去重规则。

### 10.3 非目标日志

输入:

```text
不包含 vvv=1 的日志行
```

期望:

- 不写入 `raw_log_event`。
- offset 正常推进。

### 10.4 日志截断

输入:

```text
log_state.offset 大于当前 access_chfs.log size
```

期望:

- offset 重置为 0。
- 当前日志从头处理。
- 已存在事件不重复入库。

### 10.5 30 分钟去重

输入:

```text
同一 file_key 分别在 10:00、10:05、10:40 访问
```

期望:

- `raw_log_event` 有 3 条。
- `file_visit` 有 2 条。

## 11. 风险与约束

- SQLite 单写多读适合当前本地脚本场景，但不适合高并发写入。
- Nginx 日志格式变化会影响解析，需要集中维护解析函数。
- 如果多个任务同时运行 `ingest_log.py tail`，可能产生 offset 竞争；应避免并发运行，或后续加进程锁。
- 日志路径、CHFS 根目录、CHFS URL 目前仍是本机配置，应继续通过 bat 参数或配置文件传入。

## 12. 推荐默认路径

```text
Nginx 日志:
E:\Developer\nginx\nginx-1.22.1\logs\access_chfs.log

SQLite:
E:\Developer\pix-ffmpig\py\analyze\visit_stats.db

CHFS 根目录:
I:\files

CHFS URL:
http://192.168.28.67:9527

前端输出目录:
H:\tmp\local\wind-sum
I:\files\wind-sum
```

