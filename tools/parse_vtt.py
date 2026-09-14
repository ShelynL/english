#!/usr/bin/env python3
"""把 yt-dlp 下载的 VTT 字幕清洗成 {"t": "MM:SS", "it": "句子"} 列表。

用法:
    python3 tools/parse_vtt.py lessons/raw/video.it.vtt            # 打印前 20 条
    python3 tools/parse_vtt.py in.vtt -o out.json --merge          # 合并成完整句子后写 JSON
    python3 tools/parse_vtt.py in.vtt --preview 40

处理 YouTube 自动字幕的常见脏格式:
  - WEBVTT / Kind: / Language: 头部
  - 时间戳后的 align:start position:0%
  - <00:00:01.234><c>word</c> 词级时间标签
  - 滚动字幕: 每条 cue 重复上一条的最后一行
  - &nbsp; 等 HTML 实体
仅依赖标准库。
"""
import argparse
import html
import json
import re
import sys

TS_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{2}):(\d{2})[.,](\d{3})\s*-->")
TAG_RE = re.compile(r"<[^>]*>")
WS_RE = re.compile(r"\s+")
SENT_END_RE = re.compile(r"[.!?…][\"'”»)]*$")


def _fmt_ts(h, m, s):
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def clean_line(line):
    """去掉标签、实体、多余空白。"""
    line = TAG_RE.sub("", line)
    line = html.unescape(line).replace(" ", " ")
    return WS_RE.sub(" ", line).strip()


def parse_vtt(path):
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return parse_vtt_text(content)


def parse_vtt_text(content):
    content = content.replace("\r\n", "\n").lstrip("﻿")
    blocks = re.split(r"\n\n+", content)
    entries = []
    last_line = None
    for b in blocks:
        lines = b.split("\n")
        ts = None
        text_lines = []
        for l in lines:
            m = TS_RE.match(l.strip())
            if m:
                h = int(m.group(1) or 0)
                ts = _fmt_ts(h, int(m.group(2)), int(m.group(3)))
                continue
            if ts is None:
                continue  # 时间戳之前的内容 (cue 编号 / 头部) 一律跳过
            cl = clean_line(l)
            if cl and not cl.isdigit():
                text_lines.append(cl)
        if ts is None or not text_lines:
            continue
        # 滚动字幕去重: 与上一条已输出行相同的行丢掉
        fresh = []
        for cl in text_lines:
            if cl == last_line:
                continue
            fresh.append(cl)
            last_line = cl
        if fresh:
            entries.append({"t": ts, "it": " ".join(fresh)})
    return entries


def merge_sentences(entries):
    """把片段按 . ! ? 合并成完整句子, 时间戳取首个片段。"""
    merged = []
    buf = []
    start = None
    for e in entries:
        if not buf:
            start = e["t"]
        buf.append(e["it"])
        if SENT_END_RE.search(e["it"]):
            merged.append({"t": start, "it": " ".join(buf)})
            buf = []
    if buf:
        merged.append({"t": start, "it": " ".join(buf)})
    return merged


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("vtt", help="输入的 .vtt 文件")
    ap.add_argument("-o", "--out", help="输出 JSON 路径 (不给则只打印预览)")
    ap.add_argument("--merge", action="store_true", help="按句末标点合并成完整句子")
    ap.add_argument("--preview", type=int, default=20, help="打印前 N 条 (默认 20)")
    args = ap.parse_args(argv)

    entries = parse_vtt(args.vtt)
    if args.merge:
        entries = merge_sentences(entries)
    if not entries:
        print("没有解析到任何字幕行, 请检查文件格式。", file=sys.stderr)
        return 1

    for e in entries[: args.preview]:
        print(f"[{e['t']}] {e['it']}")
    if len(entries) > args.preview:
        print(f"... 共 {len(entries)} 条")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"已写入 {args.out} ({len(entries)} 条)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
