# 意大利语视频课程生成流水线

把一个 YouTube 意大利语视频变成一份「五步法」互动课程 HTML。课程页面为意大利语 ↔ 英语对照，界面与讲解全部英文；本 README 是给维护者看的中文说明。

```
yt-dlp 拉字幕 → tools/parse_vtt.py 清洗成句子列表 → Claude 写 lesson.json → tools/build_lesson.py 生成 HTML
```

## 目录

```
tools/
  download_subs.sh   本机用：yt-dlp 下载意大利语字幕（官方优先，其次自动字幕；无字幕时提示 whisper 回退）
  parse_vtt.py       VTT → JSON 句子列表（去 <c> 标签、去滚动重复、解实体，可按标点合并成整句）
  build_lesson.py    lesson.json + template.html → lessons/<主题>_<日期>.html（会校验数据）
  template.html      五步法页面模板（CSS 变量 + 5 个 panel + 交互 JS）
  test_tools.py      单元测试
  requirements.txt   只有 yt-dlp（解析与生成只用标准库）
lessons/
  <主题>_<日期>.html         成品课程，直接双击用浏览器打开即可
  raw/<主题>.it.vtt          原始字幕
  raw/<主题>_sentences.json  清洗后的句子列表
  raw/<主题>_lesson.json     手写的课程数据（每课只需改这一份）
```

## 每课的操作步骤

**1. 下载字幕（在能访问 YouTube 的电脑上）**

```bash
pip install -U yt-dlp
bash tools/download_subs.sh "<YouTube链接>" everyeye_tech      # 生成 lessons/raw/everyeye_tech.it.vtt
```

视频没有任何字幕时，脚本会打印 `yt-dlp -x --audio-format mp3` + `whisper --language it` 的回退命令。

**2. 清洗成句子列表**

```bash
python3 tools/parse_vtt.py lessons/raw/everyeye_tech.it.vtt --merge -o lessons/raw/everyeye_tech_sentences.json
```

`--merge` 按 `. ! ?` 把字幕碎片拼成完整句；不加则保持每条 cue 一行。`--preview 40` 控制打印条数。

**3. 让 Claude 写 lesson.json**

把 `lessons/raw/everyeye_tech_sentences.json` 和本 README 的「lesson.json 结构」一起发给 Claude Code，让它：
挑 6 句语法/词汇有代表性的句子 → 补英文翻译 → 出 3 道 MCQ 理解题（英文） → 选 6–8 个挖空词 + 2 个干扰词 → 写英文的语法卡片和词汇卡片，
保存为 `lessons/raw/everyeye_tech_lesson.json`。

**4. 生成课程**

```bash
python3 tools/build_lesson.py lessons/raw/everyeye_tech_lesson.json
# → lessons/everyeye_tech_2026-09-14.html（文件名取自 meta.slug + meta.date）
```

## 五步法页面结构

| 步骤 | 内容 | 用到的数据 |
|---|---|---|
| 01 Read & Listen | 6 句意大利语 + 英语对照，每句 ▶ TTS 朗读，可播放全文 | `sentences` |
| 02 Speak It | 只显示英文，用户写意大利语，「对照原文」逐词标绿/标红，可翻页 | `sentences` |
| 03 Listening Quiz | 播放全文 TTS（不显示文字），3 道单选题，检查后标绿/红并计分 | `mcqs` |
| 04 Dictation Cloze | 6 句原文挖空（每个词只挖第一次出现），词库 = 挖空词 + 2 干扰词，点词填入，逐空比对计分 | `blanks` `distractors` |
| 05 Deep Dive | 语法卡片（用途 / 结构 / 原文例句 / 讲解）+ 词汇卡片网格 + 「现在轮到你」造句 | `grammar` `vocab` |

朗读用浏览器自带的 `speechSynthesis`（意大利语 voice），无需联网；页面里的 Google Fonts 链接离线时自动回退系统字体。

## lesson.json 结构

```jsonc
{
  "meta": {
    "slug": "al_mercato",            // 文件名用，只能字母数字下划线连字符
    "date": "2026-09-14",            // YYYY-MM-DD
    "eyebrow": "Italiano · Lezione", // 标题上方的小字
    "title": "At the Market · Al mercato",
    "tags": ["A2", "Shopping dialogue"],
    "source_url": "https://www.youtube.com/watch?v=..."
  },
  "sentences": [                     // 恰好 6 句
    { "t": "00:02", "it": "Vorrei un chilo di pomodori, per favore.", "en": "I'd like a kilo of tomatoes, please." }
  ],
  "mcqs": [                          // 恰好 3 题，a 是正确选项下标（从 0 起）
    { "q": "Question in English", "opts": ["A", "B", "C"], "a": 1 }
  ],
  "blanks": ["desidera", "chilo"],   // 6–8 个，必须能在 6 句原文里整词找到，不重复
  "distractors": ["prendo", "sempre"], // 恰好 2 个，不能出现在原文里
  "grammar": [                       // ≥1 张
    { "title": "Vorrei…", "use": "when to use it", "structure": "form", "example": "sentence from the video", "explain": "explanation (English)" }
  ],
  "vocab": [                         // ≥1 张
    { "term": "desiderare", "mean": "to want, to wish (English gloss)" }
  ]
}
```

`build_lesson.py` 会检查以上所有约束，不满足时以非 0 退出并逐条列出问题。

## 示例

`lessons/al_mercato_2026-09-14.html` 由 `lessons/raw/al_mercato_*` 生成，字幕是手写的示例 VTT（模拟 YouTube 自动字幕的 `<c>` 标签、滚动重复行、HTML 实体），用来跑通并测试整条流水线。

## 测试

```bash
python3 -m unittest tools/test_tools.py -v
```

## 换模板

生成器与模板之间只有 4 个占位符：`{{TITLE}}`、`{{EYEBROW}}`、`{{TAGS}}`、`/*__LESSON_DATA__*/`（会被替换成 `const meta/sentences/mcqs/blanks/distractors/fill/grammar/vocab = …;`）。
换一套页面设计时保留这 4 个占位符和上面几个变量名即可，用 `-t 你的模板.html` 指定。
