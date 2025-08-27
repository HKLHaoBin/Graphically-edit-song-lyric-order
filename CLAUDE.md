# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于 FastAPI + 原生前端的 .lys 歌词可视化顺序编辑器，支持：
- 多选拖放调整歌词 token 顺序（保留时间戳）
- 可编辑行前缀（如 `[4]`）
- 复制/粘贴所选 token 或整行
- 导入/导出 `.lys` 文件（原格式不丢失）
- 内置播放器，支持音频/视频文件或时钟模式播放

## 技术栈

- **后端**: FastAPI (Python 3.10+)
- **前端**: 原生 HTML/CSS/JavaScript（零依赖）
- **部署**: 支持 Docker 和 GitHub Pages

## 开发命令

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动开发服务器
```bash
python app.py
```
默认监听：`http://localhost:8000`

### Docker 构建和运行
```bash
# 构建镜像
docker build -t lys-editor .

# 运行容器
docker run -p 8000:8000 lys-editor
```

## 项目结构

```
├── app.py              # FastAPI 后端服务器（单文件应用）
├── index.html          # 前端界面（包含所有CSS和JS）
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 容器配置
├── *.lys              # 示例歌词文件
└── README.md          # 详细使用说明
```

## 核心API端点

- `GET /` - 返回前端页面
- `POST /api/import` - 导入 .lys 文件
- `GET /api/lyrics?doc_id=` - 获取文档数据
- `GET /api/export?doc_id=` - 导出 .lys 文件
- `POST /api/move` - 拖放移动 token
- `POST /api/undo` / `POST /api/redo` - 撤销/重做
- `POST /api/set_prefix` - 设置行前缀
- `POST /api/insert_tokens` - 粘贴插入 tokens
- `POST /api/newline` - 插入新行
- `POST /api/sort_lines` - 按时间排序歌词行
- `GET /health` - 健康检查

## 关键文件说明

### app.py: 后端核心（单文件架构）
- `parse_lys()` / `dump_lys()` - .lys 文件解析和导出（支持半/全角括号）
- `apply_move()` - 拖放移动算法核心（保留时间戳）
- 歌词行排序功能（按第一个token开始时间）
- 内存文档管理和版本控制（内存存储，重启丢失）
- 撤销/重做栈实现
- 文档版本冲突检测（409错误）

### index.html: 前端界面（零依赖原生实现）
- 原生 JavaScript 实现拖放交互（多选、行级拖放）
- 播放器逻辑（媒体文件 + 时钟模式）
- 实时高亮显示（基于时间戳）
- 复制/粘贴功能（快捷键支持）
- 行前缀编辑功能
- 歌词行排序功能

## 开发注意事项

1. **文档版本控制**: 所有编辑操作都需要提供 `base_version` 参数，版本冲突返回 409
2. **时间戳保留**: 前端不显示时间戳，但所有移动操作都会保留原时间戳
3. **内存存储**: 当前使用内存存储文档，重启服务器会丢失数据
4. **跨域支持**: 已配置 CORS 允许跨域访问
5. **文件编码**: 支持 UTF-8 编码，自动处理解码错误

## 测试建议

- 导入示例 .lys 文件进行功能测试
- 测试拖放移动、撤销重做、复制粘贴功能
- 验证播放器高亮功能（带媒体文件和不带媒体文件）
- 检查导出文件是否保留原始格式和时间戳
- 测试版本冲突处理机制
- 测试歌词行排序功能

## 架构特点

- **单文件后端**: app.py 包含所有后端逻辑，便于维护
- **零依赖前端**: 纯原生 HTML/CSS/JS，无框架依赖
- **内存存储**: 简单快速，适合临时编辑会话
- **实时协作**: 基于版本号的乐观并发控制
- **格式兼容**: 支持 .lys 文件格式的完整解析和导出