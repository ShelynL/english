#!/usr/bin/env bash
# 在 *能访问 YouTube 的机器* 上运行 (Claude Code 云端沙盒连不上 YouTube)。
# 用法: bash tools/download_subs.sh "<YouTube链接>" <主题slug>
#   例: bash tools/download_subs.sh "https://www.youtube.com/watch?v=xxxx" everyeye_tech
# 产物: lessons/raw/<slug>.it.vtt   (官方字幕优先, 没有就用自动生成字幕)
set -euo pipefail

URL="${1:?用法: bash tools/download_subs.sh <YouTube链接> <主题slug>}"
SLUG="${2:?缺少主题 slug (只用字母数字下划线, 会用作文件名)}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$ROOT/lessons/raw"
mkdir -p "$OUT_DIR"

if ! command -v yt-dlp >/dev/null 2>&1; then
  echo "未找到 yt-dlp, 先安装:  pip install -U yt-dlp   (或 brew install yt-dlp)" >&2
  exit 1
fi

yt-dlp --write-sub --write-auto-sub --sub-lang it --skip-download --sub-format vtt \
  -o "$OUT_DIR/$SLUG" "$URL"

VTT="$OUT_DIR/$SLUG.it.vtt"
if [[ -f "$VTT" ]]; then
  echo "字幕已保存: $VTT"
  echo "下一步:  python3 tools/parse_vtt.py \"$VTT\" --merge -o \"$OUT_DIR/${SLUG}_sentences.json\""
  exit 0
fi

cat >&2 <<EOF
没有拿到意大利语字幕 (视频可能既无官方字幕也无自动字幕)。
回退方案: 先抽音频, 再用 whisper 本地转录成 VTT:

  yt-dlp -x --audio-format mp3 -o "$OUT_DIR/$SLUG.%(ext)s" "$URL"
  pip install -U openai-whisper          # 需要 ffmpeg
  whisper "$OUT_DIR/$SLUG.mp3" --language it --model small --output_format vtt --output_dir "$OUT_DIR"
  mv "$OUT_DIR/$SLUG.vtt" "$VTT"

然后同样跑 parse_vtt.py。
EOF
exit 2
