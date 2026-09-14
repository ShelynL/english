#!/usr/bin/env python3
"""把手写的 lesson.json 灌进 template.html，生成一份五步法课程 HTML。

用法:
    python3 tools/build_lesson.py lessons/raw/al_mercato_lesson.json
    python3 tools/build_lesson.py lesson.json -t tools/template.html -o lessons/xxx_2026-09-14.html

lesson.json 结构见 lessons/README.md。校验失败时以非 0 退出并打印原因。
仅依赖标准库。
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(HERE, "template.html")
DEFAULT_OUT_DIR = os.path.join(os.path.dirname(HERE), "lessons")

N_SENTENCES = 6
N_MCQ = 3
MIN_BLANKS, MAX_BLANKS = 6, 8
N_DISTRACTORS = 2


class LessonError(ValueError):
    pass


def _word_pattern(word):
    # 整词匹配，忽略大小写；允许词前后是空格、标点或撇号 (Quant'è)
    return re.compile(r"(?<![\w'])" + re.escape(word) + r"(?![\w])", re.IGNORECASE)


def validate(lesson):
    errs = []

    meta = lesson.get("meta") or {}
    for k in ("slug", "date", "title"):
        if not str(meta.get(k, "")).strip():
            errs.append(f"meta.{k} 不能为空")
    if meta.get("slug") and not re.fullmatch(r"[A-Za-z0-9_\-]+", meta["slug"]):
        errs.append("meta.slug 只能用字母、数字、下划线、连字符 (用作文件名)")
    if meta.get("date") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["date"]):
        errs.append("meta.date 必须是 YYYY-MM-DD")

    sents = lesson.get("sentences")
    if not isinstance(sents, list) or len(sents) != N_SENTENCES:
        errs.append(f"sentences 必须恰好 {N_SENTENCES} 句 (现在 {len(sents) if isinstance(sents, list) else '不是列表'})")
        sents = sents if isinstance(sents, list) else []
    for i, s in enumerate(sents):
        for k in ("t", "it", "en"):
            if not str((s or {}).get(k, "")).strip():
                errs.append(f"sentences[{i}].{k} 不能为空")

    mcqs = lesson.get("mcqs")
    if not isinstance(mcqs, list) or len(mcqs) != N_MCQ:
        errs.append(f"mcqs 必须恰好 {N_MCQ} 题 (现在 {len(mcqs) if isinstance(mcqs, list) else '不是列表'})")
        mcqs = mcqs if isinstance(mcqs, list) else []
    for i, m in enumerate(mcqs):
        opts = (m or {}).get("opts")
        if not str((m or {}).get("q", "")).strip():
            errs.append(f"mcqs[{i}].q 不能为空")
        if not isinstance(opts, list) or len(opts) < 2:
            errs.append(f"mcqs[{i}].opts 至少 2 个选项")
        elif not isinstance((m or {}).get("a"), int) or not (0 <= m["a"] < len(opts)):
            errs.append(f"mcqs[{i}].a 必须是 0..{len(opts) - 1} 的整数")

    blanks = lesson.get("blanks")
    if not isinstance(blanks, list) or not (MIN_BLANKS <= len(blanks) <= MAX_BLANKS):
        errs.append(f"blanks 必须 {MIN_BLANKS}-{MAX_BLANKS} 个 (现在 {len(blanks) if isinstance(blanks, list) else '不是列表'})")
        blanks = blanks if isinstance(blanks, list) else []
    if len(set(b.lower() for b in blanks if isinstance(b, str))) != len(blanks):
        errs.append("blanks 里有重复的词")

    all_it = "\n".join(str((s or {}).get("it", "")) for s in sents)
    for b in blanks:
        if not isinstance(b, str) or not b.strip():
            errs.append("blanks 里有空值")
        elif not _word_pattern(b).search(all_it):
            errs.append(f"blanks 里的 '{b}' 在 6 句原文中找不到 (需整词匹配)")

    dis = lesson.get("distractors")
    if not isinstance(dis, list) or len(dis) != N_DISTRACTORS:
        errs.append(f"distractors 必须恰好 {N_DISTRACTORS} 个")
        dis = dis if isinstance(dis, list) else []
    for d in dis:
        if not isinstance(d, str) or not d.strip():
            errs.append("distractors 里有空值")
        elif _word_pattern(d).search(all_it):
            errs.append(f"干扰词 '{d}' 出现在原文里, 不算干扰项")
        elif d.lower() in {b.lower() for b in blanks if isinstance(b, str)}:
            errs.append(f"干扰词 '{d}' 与挖空词重复")

    grammar = lesson.get("grammar")
    if not isinstance(grammar, list) or not grammar:
        errs.append("grammar 至少 1 张卡片")
    else:
        for i, g in enumerate(grammar):
            for k in ("title", "use", "structure", "example", "explain"):
                if not str((g or {}).get(k, "")).strip():
                    errs.append(f"grammar[{i}].{k} 不能为空")

    vocab = lesson.get("vocab")
    if not isinstance(vocab, list) or not vocab:
        errs.append("vocab 至少 1 张卡片")
    else:
        for i, v in enumerate(vocab):
            for k in ("term", "mean"):
                if not str((v or {}).get(k, "")).strip():
                    errs.append(f"vocab[{i}].{k} 不能为空")

    if errs:
        raise LessonError("lesson.json 校验失败:\n  - " + "\n  - ".join(errs))


def build_fill(sentences, blanks):
    """为每句生成 [文本, {i, a}, 文本, ...] 片段; 每个挖空词只挖第一次出现的位置。"""
    remaining = list(blanks)
    order = {}
    segs = []
    for s in sentences:
        text = s["it"]
        cuts = []  # (start, end, word)
        for b in list(remaining):
            m = _word_pattern(b).search(text)
            if m:
                cuts.append((m.start(), m.end(), text[m.start():m.end()]))
                remaining.remove(b)
        cuts.sort()
        parts = []
        pos = 0
        for st, en, w in cuts:
            if st > pos:
                parts.append(text[pos:st])
            order[w] = len(order)
            parts.append({"i": len(order) - 1, "a": w})
            pos = en
        if pos < len(text):
            parts.append(text[pos:])
        segs.append(parts)
    if remaining:  # validate() 已保证找得到, 这里只是保险
        raise LessonError(f"挖空词未能定位: {remaining}")
    return segs


def _js(obj):
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _esc_html(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def render(lesson, template):
    validate(lesson)
    meta = lesson["meta"]
    fill = build_fill(lesson["sentences"], lesson["blanks"])
    data = "\n".join([
        f"const meta = {_js(meta)};",
        f"const sentences = {_js(lesson['sentences'])};",
        f"const mcqs = {_js(lesson['mcqs'])};",
        f"const blanks = {_js(lesson['blanks'])};",
        f"const distractors = {_js(lesson['distractors'])};",
        f"const fill = {_js(fill)};",
        f"const grammar = {_js(lesson['grammar'])};",
        f"const vocab = {_js(lesson['vocab'])};",
    ])
    tags = "".join(f'<span class="tag">{_esc_html(t)}</span>' for t in meta.get("tags", []))
    for ph in ("{{TITLE}}", "{{EYEBROW}}", "{{TAGS}}", "/*__LESSON_DATA__*/"):
        if ph not in template:
            raise LessonError(f"模板缺少占位符 {ph}")
    return (template
            .replace("{{TITLE}}", _esc_html(meta["title"]))
            .replace("{{EYEBROW}}", _esc_html(meta.get("eyebrow", "Italiano · Lezione")))
            .replace("{{TAGS}}", tags)
            .replace("/*__LESSON_DATA__*/", data))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lesson", help="手写的 lesson.json")
    ap.add_argument("-t", "--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("-o", "--out", help="输出 HTML (默认 lessons/<slug>_<date>.html)")
    args = ap.parse_args(argv)

    try:
        with open(args.lesson, encoding="utf-8") as f:
            lesson = json.load(f)
    except json.JSONDecodeError as e:
        print(f"lesson.json 不是合法 JSON: {e}", file=sys.stderr)
        return 2
    with open(args.template, encoding="utf-8") as f:
        template = f.read()

    try:
        html_out = render(lesson, template)
    except LessonError as e:
        print(str(e), file=sys.stderr)
        return 1

    out = args.out or os.path.join(DEFAULT_OUT_DIR, f"{lesson['meta']['slug']}_{lesson['meta']['date']}.html")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"已生成 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
