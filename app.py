# app.py
# 单文件后端：提供 .lys 解析/移动/导出 API，并直接服务 index.html 网页
# 依赖：pip install fastapi uvicorn python-multipart
# 第一个正式版本

import os
import re
import uuid
import copy
from typing import Any, Dict, List, Tuple

from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.responses import PlainTextResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Lys Lyrics Editor (Drag&Drop)", version="0.2.0")

# 允许跨域（你也可以按需收紧）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 内存数据库与工具
# =========================
DB_DOCS: Dict[str, Dict[str, Any]] = {}          # 文档
UNDO_STACK: Dict[str, List[Dict[str, Any]]] = {} # 撤销栈
REDO_STACK: Dict[str, List[Dict[str, Any]]] = {} # 重做栈

def new_id() -> str:
    return uuid.uuid4().hex

def deep_clone(obj):
    return copy.deepcopy(obj)

# =========================
# .lys 解析与导出
# =========================
HEADER_PREFIX_RE = re.compile(r'^\[(ti|ar|al):', re.IGNORECASE)
LINE_PREFIX_RE = re.compile(r'^\[(\d+)\]')
# 支持半/全角括号：(…) 或 （…） ；token 形如  文本(开始,时长)
TOKEN_RE = re.compile(r'(.*?)[(（](\d+),(\d+)[)）]')

def parse_lys(raw_text: str) -> Dict[str, Any]:
    """
    将 .lys 文本解析为结构化文档：
    doc = { id, version, lines: [ {id, prefix, is_meta, tokens:[{id, ts, text}]} ] }
    """
    lines: List[Dict[str, Any]] = []
    for raw_line in raw_text.splitlines():
        s = raw_line.rstrip("\r\n")
        if not s:
            lines.append({"id": new_id(), "prefix": "", "is_meta": False, "tokens": []})
            continue

        # 元信息行（头部标签）原样保留
        if HEADER_PREFIX_RE.match(s):
            lines.append({
                "id": new_id(),
                "prefix": "",
                "is_meta": True,
                "tokens": [{"id": new_id(), "ts": "", "text": s}]
            })
            continue

        # 捕获行前缀（如 [4] 或 []）
        prefix = ""
        rest = s
        m = LINE_PREFIX_RE.match(s)
        if m:
            prefix = m.group(0)
            rest = s[m.end():]
        # 支持空括号 []
        elif s.startswith("[]"):
            prefix = "[]"
            rest = s[2:]

        # 解析 token
        tokens: List[Dict[str, str]] = []
        for m in TOKEN_RE.finditer(rest):
            text = m.group(1)
            start = m.group(2)
            dur = m.group(3)
            tokens.append({"id": new_id(), "ts": f"{start},{dur}", "text": text})

        if tokens:
            lines.append({"id": new_id(), "prefix": prefix, "is_meta": False, "tokens": tokens})
        else:
            # 没解析出 token，则整行作为 meta 文本保存
            lines.append({
                "id": new_id(),
                "prefix": "",
                "is_meta": True,
                "tokens": [{"id": new_id(), "ts": "", "text": s}]
            })

    return {"id": new_id(), "version": 0, "lines": lines}

def dump_lys(doc: Dict[str, Any]) -> str:
    """结构化文档还原为 .lys 文本。meta 行原样输出；歌词行输出 prefix + "text(ts)" 串联。"""
    out_lines: List[str] = []
    for line in doc["lines"]:
        if line.get("is_meta"):
            out_lines.append("".join(tok["text"] for tok in line.get("tokens", [])))
            continue
        buf = [line["prefix"]] if line.get("prefix") else []
        for tok in line.get("tokens", []):
            ts = tok.get("ts", "")
            text = tok.get("text", "")
            buf.append(f"{text}({ts})" if ts else text)
        out_lines.append("".join(buf))
    return "\n".join(out_lines)

# =========================
# 移动算法
# =========================
class MoveError(Exception):
    pass

def find_line(doc: Dict[str, Any], line_id: str) -> Tuple[int, Dict[str, Any]]:
    for i, ln in enumerate(doc["lines"]):
        if ln["id"] == line_id:
            return i, ln
    raise MoveError(f"line not found: {line_id}")

def find_token_index(line: Dict[str, Any], token_id: str) -> int:
    for i, tok in enumerate(line["tokens"]):
        if tok["id"] == token_id:
            return i
    raise MoveError(f"token not found in line {line['id']}: {token_id}")

def normalize_selection(doc: Dict[str, Any], selection: List[Dict[str, str]]):
    """selection: [{line_id, start_token_id, end_token_id}, ...]  ->  (li, ti, token) 列表（文档顺序）"""
    collected: List[Tuple[int,int,Dict[str,str]]] = []
    for rng in selection:
        li, line = find_line(doc, rng["line_id"])
        a = find_token_index(line, rng["start_token_id"])
        b = find_token_index(line, rng["end_token_id"])
        if a > b: a, b = b, a
        for ti in range(a, b + 1):
            collected.append((li, ti, line["tokens"][ti]))
    collected.sort(key=lambda t: (t[0], t[1]))
    return collected

def apply_move(doc: Dict[str, Any], selection: List[Dict[str, str]], target: Dict[str, Any], delete_empty_lines: bool = True) -> None:
    """
    target:
      - {"type":"anchor","line_id":...,"anchor_token_id":...,"position":"before"|"after"}
      - {"type":"newline","insert_after_line_id": <line_id | None>}
    """
    if not selection:
        return
    collected = normalize_selection(doc, selection)
    if not collected:
        return

    selected_ids = {tok["id"] for _, _, tok in collected}

    # 从源行删除（后到前）
    by_line: Dict[int, List[int]] = {}
    for li, ti, _ in collected:
        by_line.setdefault(li, []).append(ti)
    for li, idxs in sorted(by_line.items(), key=lambda kv: kv[0], reverse=True):
        line = doc["lines"][li]
        for ti in sorted(idxs, reverse=True):
            del line["tokens"][ti]

    # 解析目标
    if target.get("type") == "anchor":
        t_li, t_line = find_line(doc, target["line_id"])
        anchor_idx = find_token_index(t_line, target["anchor_token_id"])
        if t_line["tokens"][anchor_idx]["id"] in selected_ids:
            raise MoveError("anchor token is within the selection")
        insert_at = anchor_idx if target.get("position") == "before" else anchor_idx + 1

    elif target.get("type") == "newline":
        new_line = {"id": new_id(), "prefix": "", "is_meta": False, "tokens": []}
        after_id = target.get("insert_after_line_id")
        if after_id:
            idx, _ = find_line(doc, after_id)
            doc["lines"].insert(idx + 1, new_line)
            t_line = new_line
            insert_at = 0
        else:
            doc["lines"].insert(0, new_line)
            t_line = new_line
            insert_at = 0
    elif target.get("type") == "line":
        # 直接按行的头/尾插入（适配对空行的放置）
        t_li, t_line = find_line(doc, target["line_id"])
        pos = target.get("position", "end")
        if pos not in ("start", "end"):
            raise MoveError("invalid line position")
        insert_at = 0 if pos == "start" else len(t_line["tokens"])
    else:
        raise MoveError("invalid target type")

    # 插入（保持原顺序，时间戳随 token 一起移动）
    moving_tokens = [tok for _, _, tok in collected]
    for offset, tok in enumerate(moving_tokens):
        t_line["tokens"].insert(insert_at + offset, tok)

    # 清理空行（不删 meta 行）
    if delete_empty_lines:
        doc["lines"] = [ln for ln in doc["lines"] if (ln.get("is_meta") or len(ln["tokens"]) > 0)]

# =========================
# 路由（网页与 API）
# =========================
@app.get("/", response_class=HTMLResponse)
def serve_index():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "index.html")
    if not os.path.exists(path):
        return HTMLResponse("<h1>index.html 未找到</h1>", status_code=404)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return HTMLResponse(f.read(), status_code=200)

@app.post("/api/import")
async def api_import(file: UploadFile = File(...)):
    raw_bytes = await file.read()
    try:
        raw = raw_bytes.decode("utf-8")
    except Exception:
        raw = raw_bytes.decode("utf-8", errors="ignore")
    doc = parse_lys(raw)
    DB_DOCS[doc["id"]] = doc
    UNDO_STACK[doc["id"]] = []
    REDO_STACK[doc["id"]] = []
    return doc

@app.get("/api/lyrics")
def api_get(doc_id: str):
    doc = DB_DOCS.get(doc_id)
    if not doc:
        raise HTTPException(404, "document not found")
    return doc

@app.get("/api/export", response_class=PlainTextResponse)
def api_export(doc_id: str):
    doc = DB_DOCS.get(doc_id)
    if not doc:
        raise HTTPException(404, "document not found")
    text = dump_lys(doc)
    return PlainTextResponse(text, media_type="text/plain; charset=utf-8")

@app.post("/api/move")
def api_move(payload: Dict[str, Any] = Body(...)):
    document_id = payload.get("document_id")
    base_version = payload.get("base_version")
    selection = payload.get("selection") or []
    target = payload.get("target") or {}

    doc = DB_DOCS.get(document_id)
    if not doc:
        raise HTTPException(404, "document not found")
    if doc["version"] != base_version:
        raise HTTPException(409, "version conflict")

    before = deep_clone(doc)
    try:
        apply_move(doc, selection, target)
    except MoveError as e:
        raise HTTPException(409, str(e))

    doc["version"] += 1
    UNDO_STACK[doc["id"]].append(before)
    REDO_STACK[doc["id"]].clear()
    return doc

@app.post("/api/undo")
def api_undo(doc_id: str):
    stack = UNDO_STACK.get(doc_id) or []
    if not stack:
        raise HTTPException(400, "nothing to undo")
    curr = DB_DOCS[doc_id]
    prev = stack.pop()
    REDO_STACK[doc_id].append(deep_clone(curr))
    DB_DOCS[doc_id] = prev
    return prev

@app.post("/api/redo")
def api_redo(doc_id: str):
    stack = REDO_STACK.get(doc_id) or []
    if not stack:
        raise HTTPException(400, "nothing to redo")
    curr = DB_DOCS[doc_id]
    nxt = stack.pop()
    UNDO_STACK[doc_id].append(deep_clone(curr))
    DB_DOCS[doc_id] = nxt
    return nxt

# ===== 额外编辑操作：新建空行 / 设置前缀 / 插入（粘贴）tokens =====
@app.post("/api/newline")
def api_newline(payload: Dict[str, Any] = Body(...)):
    """
    在指定行之后插入一个空的歌词行（非 meta）。
    payload: { document_id, base_version, insert_after_line_id? }
    若 insert_after_line_id 为空，则在文档开头插入。
    """
    document_id = payload.get("document_id")
    base_version = payload.get("base_version")
    after_id = payload.get("insert_after_line_id")

    doc = DB_DOCS.get(document_id)
    if not doc:
        raise HTTPException(404, "document not found")
    if doc["version"] != base_version:
        raise HTTPException(409, "version conflict")

    before = deep_clone(doc)
    # 构造新行并插入
    new_line = {"id": new_id(), "prefix": "", "is_meta": False, "tokens": []}
    if after_id:
        idx, _ = find_line(doc, after_id)
        doc["lines"].insert(idx + 1, new_line)
    else:
        doc["lines"].insert(0, new_line)

    doc["version"] += 1
    UNDO_STACK[doc["id"]].append(before)
    REDO_STACK[doc["id"]].clear()
    return doc

@app.post("/api/set_prefix")
def api_set_prefix(payload: Dict[str, Any] = Body(...)):
    """
    设置歌词行左侧的 [int] 前缀。payload: { document_id, base_version, line_id, prefix_int|null }
    prefix_int 为 None 或 "" 时，清空前缀；否则设置为 f"[{int}]"。
    """
    document_id = payload.get("document_id")
    base_version = payload.get("base_version")
    line_id = payload.get("line_id")
    prefix_int = payload.get("prefix_int")

    doc = DB_DOCS.get(document_id)
    if not doc:
        raise HTTPException(404, "document not found")
    if doc["version"] != base_version:
        raise HTTPException(409, "version conflict")

    li, line = find_line(doc, line_id)
    if line.get("is_meta"):
        raise HTTPException(400, "cannot set prefix for meta line")

    before = deep_clone(doc)
    if prefix_int is None or str(prefix_int) == "":
        line["prefix"] = "[]"
    else:
        try:
            n = int(prefix_int)
        except Exception:
            raise HTTPException(400, "prefix_int must be an integer or empty")
        if n < 0:
            raise HTTPException(400, "prefix_int must be >= 0")
        line["prefix"] = f"[{n}]"

    doc["version"] += 1
    UNDO_STACK[doc["id"]].append(before)
    REDO_STACK[doc["id"]].clear()
    return doc

@app.post("/api/insert_tokens")
def api_insert_tokens(payload: Dict[str, Any] = Body(...)):
    """
    在指定行的指定位置插入一组 tokens（粘贴用）。
    payload: {
      document_id, base_version,
      line_id, insert_at: int,
      tokens: [ {text: str, ts: str}, ... ]
    }
    服务器会为新 tokens 生成新的 id，保留原文本与时间戳。
    """
    document_id = payload.get("document_id")
    base_version = payload.get("base_version")
    line_id = payload.get("line_id")
    insert_at = payload.get("insert_at")
    tokens = payload.get("tokens") or []

    doc = DB_DOCS.get(document_id)
    if not doc:
        raise HTTPException(404, "document not found")
    if doc["version"] != base_version:
        raise HTTPException(409, "version conflict")

    li, line = find_line(doc, line_id)
    if line.get("is_meta"):
        raise HTTPException(400, "cannot insert tokens into meta line")
    if not isinstance(insert_at, int) or insert_at < 0 or insert_at > len(line["tokens"]):
        raise HTTPException(400, "invalid insert_at")

    before = deep_clone(doc)
    new_tokens = []
    for t in tokens:
        text = (t or {}).get("text", "")
        ts = (t or {}).get("ts", "")
        new_tokens.append({"id": new_id(), "ts": ts, "text": text})

    # 插入
    for offset, tok in enumerate(new_tokens):
        line["tokens"].insert(insert_at + offset, tok)

    doc["version"] += 1
    UNDO_STACK[doc["id"]].append(before)
    REDO_STACK[doc["id"]].clear()
    return doc

@app.post("/api/sort_lines")
def api_sort_lines(payload: Dict[str, Any] = Body(...)):
    """
    按歌词行第一个token的开始时间排序所有歌词行（非meta行）。
    payload: { document_id, base_version }
    """
    document_id = payload.get("document_id")
    base_version = payload.get("base_version")

    doc = DB_DOCS.get(document_id)
    if not doc:
        raise HTTPException(404, "document not found")
    if doc["version"] != base_version:
        raise HTTPException(409, "version conflict")

    before = deep_clone(doc)
    
    # 分离meta行和歌词行
    meta_lines = []
    lyric_lines = []
    
    for line in doc["lines"]:
        if line.get("is_meta"):
            meta_lines.append(line)
        else:
            lyric_lines.append(line)
    
    # 提取每行第一个token的开始时间进行排序
    def get_line_start_time(line):
        if not line.get("tokens") or len(line["tokens"]) == 0:
            return float('inf')  # 没有token的行排在最后
        
        first_token = line["tokens"][0]
        ts = first_token.get("ts", "")
        if not ts or "," not in ts:
            return float('inf')  # 无效时间戳排在最后
        
        try:
            start_time = int(ts.split(",")[0])
            return start_time
        except (ValueError, IndexError):
            return float('inf')  # 解析失败排在最后
    
    # 按开始时间排序歌词行
    lyric_lines.sort(key=get_line_start_time)
    
    # 重新组合行（meta行保持在原位置，歌词行按时间排序）
    # 这里简单地将meta行放在前面，歌词行按时间顺序放在后面
    doc["lines"] = meta_lines + lyric_lines
    
    doc["version"] += 1
    UNDO_STACK[doc["id"]].append(before)
    REDO_STACK[doc["id"]].clear()
    return doc

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    import time
    
    # 启动服务器后自动打开浏览器
    def open_browser():
        time.sleep(2)  # 等待服务器启动
        webbrowser.open("http://127.0.0.1:8000")
    
    # 创建线程在后台打开浏览器
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # 监听 0.0.0.0 方便局域网访问
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
