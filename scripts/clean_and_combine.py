#!/usr/bin/env python3
"""
clean_and_combine.py
OCR出力の個別Markdownファイルを結合し、md/{BookName}_combined.mdを生成する。
静的クリーニングを強化してLLMへ投げるトークンを削減する。

Usage:
    python scripts/clean_and_combine.py --book 易经
"""

import argparse
import re
import sys
from pathlib import Path

# 不要ファイルパターン
JUNK_PATTERNS = [
    "*.docx", "*.tex", "*_res.json",
    "*_layout_det_res.png", "*_layout_order_res.png",
    "*_overall_ocr_res.png", "*_preprocessed_img.png",
    "*_region_det_res.png",
]
ROOT_JUNK_PATTERNS = [
    "*_layout_det_res.png", "*_layout_order_res.png",
    "*_overall_ocr_res.png", "*_preprocessed_img.png",
    "*_region_det_res.png",
]

# ノイズ文字列（行全体にマッチしたら削除）
NOISE_LINE_PATTERNS = [
    r"^\s*扫描全能王.*$",          # OCRアプリの签名
    r"^\s*www\.[a-zA-Z0-9./-]+\s*$",   # URL
    r"^\s*https?://\S+\s*$",           # URL
    r"^\s*[\-—=═]{5,}\s*$",          # 境界線のみの行
    r"^\s*\d{1,4}\s*$",               # ページ番号のみの行
    r"^\s*[\u25a0-\u25ff\u2600-\u26ff]+\s*$",  # 記号のみ
]

# ヘッダー/フッターっぽい行（本名 or 第一語+数字のパターン）
HEADER_FOOTER_PATTERN = re.compile(
    r"^\s*第[\u4e00-\u9fff\u4e00-\u9fff\d]+章\s*$"  # 「第〇章」のみの行
    r"|^.{1,30}（\d{1,4}）\s*$"              # 染み押し形式のページ番号
)

# 脆注候補パターン：行頭に①‒⑩ または [1] [^1] など，短い行
FOOTNOTE_PATTERN = re.compile(
    r"^\s*(①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩|\[\^?\d+\]|\d+[.)）])\.?\s+.{1,120}$"
)


def parse_args():
    p = argparse.ArgumentParser(description="Combine OCR Markdown pages + 静的クリーニング")
    p.add_argument("--book",   required=True)
    p.add_argument("--paddle", default=r"E:\Books\paddle_output")
    p.add_argument("--md",     default=r"E:\Books\pdf2epub\md")
    return p.parse_args()


def cleanup_junk(book_dir: Path, paddle_base: Path):
    removed = 0
    for pattern in JUNK_PATTERNS:
        for f in book_dir.glob(pattern):
            f.unlink(); removed += 1
    for pattern in ROOT_JUNK_PATTERNS:
        for f in paddle_base.glob(pattern):
            f.unlink(); removed += 1
    print(f"  Junk files removed: {removed}")


def filter_images(text: str, book_dir: Path) -> str:
    def check_div(m):
        return m.group(0) if (book_dir / m.group(1)).exists() else ""
    def check_md(m):
        return m.group(0) if (book_dir / m.group(1)).exists() else ""
    text = re.sub(r'<div[^>]*><img\s+src="([^"]*)"[^>]*></div>', check_div, text)
    text = re.sub(r'!\[[^\]]*\]\(([^)]*)\)', check_md, text)
    return text


def static_clean(text: str) -> tuple:
    """
    LLMに投げる前にできる静的なクリーニング。
    戻り値: (クリーン後テキスト, 削除行数)
    """
    noise_patterns = [re.compile(p) for p in NOISE_LINE_PATTERNS]
    lines = text.splitlines()
    cleaned = []
    removed = 0

    for line in lines:
        # ノイズ行の除去
        is_noise = any(pat.match(line) for pat in noise_patterns)
        if is_noise:
            removed += 1
            continue
        cleaned.append(line)

    text = "\n".join(cleaned)

    # 連続空行を最別3行に制限
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    # 行頭・行末の全角スペースの整理
    text = re.sub(r"\u3000+", "", text)     # 全角スペースは削除（内字インデントはLLMに任せる）
    text = re.sub(r" {3,}", " ", text)       # 半角スペース2个以上は1つに

    return text, removed


def tag_footnotes(text: str) -> tuple:
    """
    脆注候補行に<!-- footnote -->タグを付ける。
    LLMに脆注候補を明示的に伟えるため。
    戻り値: (タグ付きテキスト, 脆注候補件数)
    """
    lines = text.splitlines()
    tagged = []
    count = 0
    for line in lines:
        if FOOTNOTE_PATTERN.match(line) and not line.strip().startswith("#"):
            tagged.append(line + "  <!-- footnote -->")
            count += 1
        else:
            tagged.append(line)
    return "\n".join(tagged), count


def main():
    args = parse_args()
    paddle_base = Path(args.paddle)
    book_dir    = paddle_base / args.book
    md_dir      = Path(args.md)
    md_dir.mkdir(parents=True, exist_ok=True)

    if not book_dir.exists():
        print(f"ERROR: {book_dir} not found", file=sys.stderr)
        sys.exit(1)

    pattern = re.compile(rf"^{re.escape(args.book)}_(\d+)\.md$")
    md_files = sorted(
        [f for f in book_dir.iterdir() if f.is_file() and pattern.match(f.name)],
        key=lambda f: int(pattern.match(f.name).group(1))
    )
    if not md_files:
        print(f"ERROR: No markdown files for '{args.book}' in {book_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"\n========================================")
    print(f" Combine & Clean: {args.book}  ({len(md_files)} pages)")
    print(f"========================================")

    parts = []
    for f in md_files:
        text = f.read_text(encoding="utf-8")
        text = filter_images(text, book_dir)
        parts.append(text)

    combined = "\n\n".join(parts)
    original_len = len(combined)

    # 静的クリーニング
    combined, noise_removed = static_clean(combined)
    print(f"  Noise lines removed : {noise_removed}")

    # 脆注候補にタグ付け
    combined, footnote_count = tag_footnotes(combined)
    print(f"  Footnote candidates : {footnote_count}")

    cleaned_len = len(combined)
    reduction = (original_len - cleaned_len) / original_len * 100 if original_len else 0
    print(f"  Chars: {original_len:,} -> {cleaned_len:,} ({reduction:.1f}% 削減)")

    out_path = md_dir / f"{args.book}_combined.md"
    out_path.write_text(combined, encoding="utf-8")
    print(f"  Saved: {out_path}")

    cleanup_junk(book_dir, paddle_base)


if __name__ == "__main__":
    main()
