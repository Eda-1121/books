#!/usr/bin/env python3
"""
fix_and_build.py
{BookName}_combined.md を整形して {BookName}_fixed.md を生成し、pandoc で EPUB をビルドする。

Usage:
    python scripts/fix_and_build.py --book 影响力 --title "影响力" --author "[美]罗伯特·西奥迪尼"
    python scripts/fix_and_build.py --book 影响力 --title "影响力" --author "[美]罗伯特·西奥迪尼" \\
        --paddle E:\\Books\\paddle_output --epub E:\\Books\\epub
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


# ──────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────
EPUB_CSS = """@charset "UTF-8";
body {
    font-family: "Noto Serif CJK SC","Source Han Serif SC","Songti SC","SimSun","STSong",serif;
    font-size: 1em; line-height: 1.8; text-align: justify;
    margin: 1em; color: #1a1a1a;
}
h1 {
    font-size: 1.6em; font-weight: bold; text-align: center;
    margin-top: 2em; margin-bottom: 1.5em;
    page-break-before: always;
    border-bottom: 1px solid #ccc; padding-bottom: 0.5em; color: #333;
}
h1:first-of-type { page-break-before: avoid; }
h2 { font-size: 1.3em; font-weight: bold; margin-top: 1.5em; margin-bottom: 0.8em; color: #444; }
h3 { font-size: 1.1em; font-weight: bold; margin-top: 1.2em; margin-bottom: 0.6em; color: #555; }
p  { text-indent: 2em; margin-top: 0.3em; margin-bottom: 0.3em; }
blockquote {
    margin: 1em 1.5em; padding: 0.6em 1em;
    border-left: 3px solid #aaa;
    background: #f9f9f9; color: #555; font-size: 0.95em;
}
img { max-width: 100%; height: auto; display: block; margin: 1em auto; }
nav#toc ol { list-style-type: none; padding-left: 0; }
nav#toc li { margin: 0.5em 0; }
"""


def parse_args():
    p = argparse.ArgumentParser(description="Fix Markdown and build EPUB")
    p.add_argument("--book",      required=True)
    p.add_argument("--paddle",    default=r"E:\Books\paddle_output")
    p.add_argument("--epub",      default=r"E:\Books\epub")
    p.add_argument("--title",     default="")
    p.add_argument("--author",    default="")
    p.add_argument("--lang",      default="zh-CN")
    p.add_argument("--min-image-kb", type=int, default=5)
    return p.parse_args()


# ──────────────────────────────────────────────
# Step 2: 画像フィルタ
# ──────────────────────────────────────────────
def filter_images(text: str, paddle_dir: Path, min_kb: int) -> tuple[str, int, int]:
    kept = removed = 0

    def check(path_str):
        nonlocal kept, removed
        p = paddle_dir / path_str
        if p.exists() and p.stat().st_size / 1024 >= min_kb:
            kept += 1
            return True
        removed += 1
        return False

    def sub_div(m):
        return m.group(0) if check(m.group(1)) else ""

    def sub_md(m):
        return m.group(0) if check(m.group(2)) else ""

    text = re.sub(r'<div[^>]*><img\s+src="([^"]*)"[^>]*></div>', sub_div, text)
    text = re.sub(r'(!\[[^\]]*\]\()([^)]*)(\))', sub_md, text)
    return text, kept, removed


# ──────────────────────────────────────────────
# Step 3: OCRノイズ除去
# ──────────────────────────────────────────────
def remove_ocr_noise(text: str) -> str:
    text = re.sub(r'(?m)^(#{1,6}\s*)\+{2,}\s*', r'\1', text)
    text = re.sub(r'(?m)^\$+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'(?m)^#{1,6}\s*\$+\s*$', '', text, flags=re.MULTILINE)
    return text


# ──────────────────────────────────────────────
# Step 4: 章見出し修正
# ──────────────────────────────────────────────
def fix_headings(text: str) -> str:
    # "# 3 谢只" -> "# 序言"
    text = re.sub(r'(?m)^#{1,6}\s*3\s*谢只', '# 序言', text)

    # "## 一 切为了您的阅读体验" -> "## 一切为了您的阅读体验"
    text = re.sub(r'(?m)^#{1,6}\s*一\s+切为了您的阅读体验', '## 一切为了您的阅读体验', text)

    # 尾声 英語サブタイトル除去
    text = re.sub(r'尾声瞬间的影响\s*Influence[^\n]*', '尾声 瞬间的影响', text)

    # Step 4a: 第N章 → h1
    # Case 1: 見出しレベルが深い
    text = re.sub(r'(?m)^#{2,6}\s*(第\d+章)', r'# \1', text)
    # Case 2: 行頭に # がない
    text = re.sub(r'(?m)^(?!#)(\s*)(第\d+章)', r'# \2', text)

    # Step 4b: 章タイトルのゴミを除去
    def clean_chapter_title(m):
        prefix = m.group(1)   # "# 第N章"
        rest   = m.group(2)   # それ以降
        # 英語サブタイトル除去
        rest = re.sub(r'\s*Influence[^\u4e00-\u9fff]*', '', rest)
        # 末尾のページ番号除去 (…27 や ...147)
        rest = re.sub(r'[\u2026\.\s]*\d+\s*$', '', rest)
        # 末尾の非CJKノイズ除去（「中的」「中的一」など短いゴミ）
        rest = re.sub(r'([\u4e00-\u9fff]{2,})\s*[\u4e00-\u9fff]{0,2}[^\u4e00-\u9fff\s]*$',
                      r'\1', rest)
        rest = rest.strip()
        return f"{prefix} {rest}" if rest else prefix

    text = re.sub(r'(?m)^(#+ 第\d+章)([^\n]*)', clean_chapter_title, text)

    # known top-level headings → h1
    for h in ['序言', '引言', '尾声', '读者报告', '影响力水平测试', '作者点评']:
        text = re.sub(rf'(?m)^{{2,6}}\s*({re.escape(h)})', rf'# \1', text)

    return text


# ──────────────────────────────────────────────
# Step 5: 章紹介ブロック削除（第1章が2回出る問題）
# 最初の「# 第1章」から次の「# 第1章」の直前まで削除
# ──────────────────────────────────────────────
def remove_intro_block(text: str) -> str:
    marker = '\n# 第1章'
    idx1 = text.find(marker)
    if idx1 < 0:
        print("  # 第1章 not found, skipping")
        return text
    idx2 = text.find(marker, idx1 + 1)
    if idx2 < 0:
        print("  Only one # 第1章 found, skipping")
        return text
    print(f"  Removed intro block ({idx2 - idx1} chars)")
    return text[:idx1] + text[idx2:]


# ──────────────────────────────────────────────
# Step 6: 専家解読ブロック → blockquote
# ──────────────────────────────────────────────
def format_expert_blocks(text: str) -> str:
    def replacer(m):
        inner = m.group(1).strip()
        inner = re.sub(r'(?m)^', '> ', inner)
        return f"\n> **《专家解读》**\n{inner}\n"

    text = re.sub(
        r'(?m)^专家[^\n]*\n解读[^\n]*\n([\s\S]*?)(?=\n\n|\n#)',
        replacer,
        text
    )
    return text


# ──────────────────────────────────────────────
# 共通クリーンアップ
# ──────────────────────────────────────────────
def common_cleanup(text: str) -> str:
    text = re.sub(r'(\r?\n){4,}', '\n\n\n', text)
    text = re.sub(r'(?m) +$', '', text)
    return text


# ──────────────────────────────────────────────
# EPUB CSS
# ──────────────────────────────────────────────
def write_css(path: Path):
    path.write_text(EPUB_CSS, encoding="utf-8")


# ──────────────────────────────────────────────
# pandoc 実行
# ──────────────────────────────────────────────
def build_epub(fixed_path: Path, epub_path: Path, css_path: Path,
               title: str, author: str, lang: str, paddle_dir: Path):
    cmd = [
        "pandoc", str(fixed_path), "-o", str(epub_path),
        "--metadata", f"title={title}",
        "--metadata", f"lang={lang}",
        "-f", "markdown", "-t", "epub3",
        f"--css={css_path}",
        f"--resource-path={paddle_dir}",
        "--epub-chapter-level=1",
        "--toc", "--toc-depth=2",
    ]
    if author:
        cmd += ["--metadata", f"author={author}"]

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


# ──────────────────────────────────────────────
# main
# ──────────────────────────────────────────────
def main():
    args = parse_args()
    paddle_dir = Path(args.paddle)
    epub_dir   = Path(args.epub)
    epub_dir.mkdir(parents=True, exist_ok=True)
    title = args.title or args.book

    print("========================================")
    print(f" Fix & Build EPUB: {title}")
    print("========================================")

    # Step 1: 読み込み
    combined_path = paddle_dir / f"{args.book}_combined.md"
    if not combined_path.exists():
        print(f"ERROR: not found -> {combined_path}", file=sys.stderr)
        sys.exit(1)
    text = combined_path.read_text(encoding="utf-8")
    print(f"[1/7] Read: {combined_path}")

    # Step 2: 画像フィルタ
    text, kept, removed = filter_images(text, paddle_dir, args.min_image_kb)
    print(f"[2/7] Images: kept={kept} removed={removed}")

    # Step 3: OCRノイズ除去
    text = remove_ocr_noise(text)
    print("[3/7] OCR noise removed")

    # Step 4: 章見出し修正
    text = fix_headings(text)
    print("[4/7] Headings fixed")

    # Step 5: 章紹介ブロック削除
    text = remove_intro_block(text)
    print("[5/7] Intro block removed")

    # Step 6: 専家解読 blockquote
    text = format_expert_blocks(text)
    print("[6/7] Expert blocks formatted")

    # 共通クリーンアップ
    text = common_cleanup(text)

    # Step 7: 保存 & EPUB生成
    fixed_path = paddle_dir / f"{args.book}_fixed.md"
    fixed_path.write_text(text, encoding="utf-8")
    print(f"[7/7] Saved: {fixed_path}")

    css_path  = paddle_dir / "epub_style.css"
    write_css(css_path)

    epub_path = epub_dir / f"{args.book}.epub"
    rc = build_epub(fixed_path, epub_path, css_path,
                    title, args.author, args.lang, paddle_dir)

    if rc == 0:
        print("\n========================================")
        print(f" EPUB created: {epub_path}")
        print("========================================")
    else:
        print(f"\n  Completed with warnings: {epub_path}")


if __name__ == "__main__":
    main()
