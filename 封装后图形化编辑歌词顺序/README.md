# .lys 歌词顺序编辑器（拖放 + 播放高亮）

一个基于 FastAPI + 原生前端的 .lys 歌词可视化顺序编辑器：
- 支持多选拖放调整歌词 token 顺序（保留时间戳）。
- 可编辑行前缀（如 `[4]`）。
- 复制/粘贴所选 token 或整行。
- 导入/导出 `.lys` 文件（原格式不丢失）。
- 内置播放器：
  - 可选加载音频/视频作为时间源。
  - 未加载媒体时支持“时钟模式”播放。
  - 按 `(开始毫秒, 持续毫秒)` 自动高亮歌词 token，离开区间自动熄灭。
  - 单击任意歌词行可从该行最早时间开始播放；支持空格键播放/暂停。

> 示例 token：`Open (14152,455)sesame(14607,528)` 表示：
> - “Open” 在 14152ms 亮起，持续 455ms；
> - “sesame” 在 14607ms 亮起，持续 528ms。


## 目录结构
- `app.py`：后端（FastAPI），提供 `.lys` 解析、拖放移动、前缀设置、粘贴插入、撤销/重做、导出等接口，并直接服务 `index.html`。
- `index.html`：前端界面与逻辑（零依赖）。
- `*.lys`：示例歌词文件。


## 快速开始
1) 安装依赖（建议 Python 3.10+）
```bash
pip install fastapi uvicorn python-multipart
```

2) 启动服务
```bash
python app.py
```
默认监听：`http://localhost:8000`

3) 打开浏览器访问
- 进入页面后：
  - 选择并导入一个 `.lys` 文件。
  - 可选加载音频/视频文件（右上角“媒体文件”输入处）。
  - 点击“播放”或按空格键开始/暂停；歌词会按时间戳高亮。


## .lys 文件格式简述
- 允许元信息头：`[ti:...]`、`[ar:...]`、`[al:...]`（原样保留）。
- 歌词行可带行前缀：`[4]`（可选）。
- 词/字 token 形如：`文本(开始毫秒,持续毫秒)`。
- 支持半/全角括号 `( )` / `（ ）`。

示例：
```text
[ti:Title]
[ar:Artist]
[al:Album]
[4]Open (14152,455)sesame(14607,528)
```


## 前端功能（`index.html`）
- 多选：`Ctrl/⌘` + 点击多个 token。
- 拖放：将所选 token 拖动到目标行的某个 token 上；落点在其左/右半决定插入“前/后”。
- 行级拖放：把所选 token 拖到整行区域左右侧，实现插入到行首/行尾。
- 行前缀：点击前缀输入框，输入数字并回车或失焦生效（清空表示无前缀）。
- 复制/粘贴：
  - 复制所选 token；若未选择 token，则复制所选整行。
  - 粘贴到：所选 token 的右侧，或所选行最左。
  - 快捷键：`Ctrl/⌘ + C`、`Ctrl/⌘ + V`。
- 播放：
  - 加载媒体（音频/视频）后按媒体时间驱动；未加载媒体时走内置时钟。
  - 单击任意歌词行 -> 从该行最早时间处开始播放。
  - 空格键播放/暂停。


## 后端 API（`app.py`）
- `GET /`：返回 `index.html`。
- `POST /api/import`：表单上传 `.lys`，返回解析后的文档。
- `GET /api/lyrics?doc_id=`：获取文档。
- `GET /api/export?doc_id=`：导出为 `.lys` 原始文本。
- `POST /api/move`：拖放移动 token。
  - body: `{ document_id, base_version, selection:[{line_id,start_token_id,end_token_id}], target:{ type:'anchor'|'line'|'newline', ... } }`
- `POST /api/newline`：在指定行后插入空行。
- `POST /api/set_prefix`：设置行前缀（数字或空）。
- `POST /api/insert_tokens`：在一行的指定位置插入一组 token（粘贴）。
- `POST /api/undo`、`POST /api/redo`：撤销/重做。
- `GET /health`：健康检查。

> 后端维护内存文档与版本号，冲突将返回 409。


## 开发备注
- 拖放/移动后端核心：`apply_move()`（保持 token 原有 `ts` 并随移动一起带走）。
- 解析/输出：`parse_lys()` / `dump_lys()`。
- 播放高亮：前端解析每个 token 的 `start,duration`，构建缓存并在 `requestAnimationFrame`/媒体事件中切换样式（`.tok.active`、`.line.playing`）。


## 兼容性
- 现代浏览器（Chrome/Edge/Safari/Firefox 最新版）。
- 视频也可作为音频使用（仅取时间轴）。


## 常见问题
- 未加载媒体也能播放吗？
  - 可以，使用“时钟模式”（页面内定时器）驱动。
- 行点击不生效？
  - 需点击行空白区域（非 token、非前缀输入框）。
- 导出是否保留时间戳？
  - 是。页面虽然不显示时间戳，但所有移动/粘贴都会保留原 `ts`，导出时完整输出。