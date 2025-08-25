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
pip install fastapi uvicorn python-multipart
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
├── app.py              # FastAPI 后端服务器
├── index.html          # 前端界面（包含所有CSS和JS）
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 容器配置
└── README.md           # 详细使用说明
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

## 关键文件说明

### app.py: 后端核心
- `parse_lys()` / `dump_lys()` - .lys 文件解析和导出
- `apply_move()` - 拖放移动算法核心
- 内存文档管理和版本控制
- 撤销/重做栈实现

### index.html: 前端界面
- 原生 JavaScript 实现拖放交互
- 播放器逻辑（媒体文件 + 时钟模式）
- 实时高亮显示
- 复制/粘贴功能

## 开发注意事项

1. **文档版本控制**: 所有编辑操作都需要提供 `base_version` 参数，版本冲突返回 409
2. **时间戳保留**: 前端不显示时间戳，但所有移动操作都会保留原时间戳
3. **内存存储**: 当前使用内存存储文档，重启服务器会丢失数据
4. **跨域支持**: 已配置 CORS 允许跨域访问

## 测试建议

- 导入示例 .lys 文件进行功能测试
- 测试拖放移动、撤销重做、复制粘贴功能
- 验证播放器高亮功能（带媒体文件和不带媒体文件）
- 检查导出文件是否保留原始格式和时间戳