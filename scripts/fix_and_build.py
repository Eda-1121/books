#!/usr/bin/env python3
"""
fix_and_build.py
md/{BookName}_combined.md を整形して md/{BookName}_fixed.md を生成し、pandoc で EPUB をビルドする。

Usage:
    python scripts/fix_and_build.py --book 易经 --title "易经" --author "著者名"
    python scripts/fix_and_build.py --book 易经 --title "易经" \
        --paddle E:\\Books\\paddle_output \
        --md     E:\\Books\\pdf2epub\\md \
        --epub   E:\\Books\\epub
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


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
    p.add_argument("--book",         required=True)
    p.add_argument("--paddle",       default=r"E:\Books\paddle_output")
    p.add_argument("--md",           default=r"E:\Books\pdf2epub\md")
    p.add_argument("--epub",         default=r"E:\Books\epub")
    p.add_argument("--title",        default="")
    p.add_argument("--author",       default="")
    p.add_argument("--lang",         default="zh-CN")
    p.add_argument("--min-image-kb", type=int, default=5)
    return p.parse_args()


def filter_images(text: str, book_dir: Path, min_kb: int) -> tuple[str, int, int]:
    kept = removed = 0

    def check(path_str):
        nonlocal kept, removed
        p = book_dir / path_str
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


def remove_ocr_noise(text: str) -> str:
    text = re.sub(r'(?m)^(#{1,6}\s*)\+{2,}\s*', r'\1', text)
    text = re.sub(r'(?m)^\$+\s*$', '', text)
    text = re.sub(r'(?m)^#{1,6}\s*\$+\s*$', '', text)
    text = re.sub(r'(?m)^[\-\*\_]{3,}\s*$', '', text)
    return text


def fix_headings(text: str) -> str:
    text = re.sub(r'(?m)^#{2,6}\s*(第\d+章)', r'# \1', text)
    text = re.sub(r'(?m)^(?!#)(\s*)(第\d+章)', r'# \2', text)
    return text


def common_cleanup(text: str) -> str:
    text = re.sub(r'(\r?\n){4,}', '\n\n\n', text)
    text = re.sub(r'(?m) +$', '', text)
    return text


def write_css(path: Path):
    path.write_text(EPUB_CSS, encoding="utf-8")


def build_epub(fixed_path: Path, epub_path: Path, css_path: Path,
               title: str, author: str, lang: str, book_dir: Path) -> int:
    cmd = [
        "pandoc", str(fixed_path), "-o", str(epub_path),
        "--metadata", f"title={title}",
        "--metadata", f"lang={lang}",
        "-f", "markdown", "-t", "epub3",
        f"--css={css_path}",
        f"--resource-path={book_dir}",
        "--epub-chapter-level=1",
        "--toc", "--toc-depth=2",
    ]
    if author:
        cmd += ["--metadata", f"author={author}"]
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def main():
    args = parse_args()
    # paddle_output/{book}/ → 画像参照およびCSSの保存先
    book_dir = Path(args.paddle) / args.book
    md_dir   = Path(args.md)
    epub_dir = Path(args.epub)
    epub_dir.mkdir(parents=True, exist_ok=True)
    title = args.title or args.book

    print("========================================")
    print(f" Fix & Build EPUB: {title}")
    print("========================================")

    combined_path = md_dir / f"{args.book}_combined.md"
    if not combined_path.exists():
        print(f"ERROR: not found -> {combined_path}", file=sys.stderr)
        sys.exit(1)
    text = combined_path.read_text(encoding="utf-8")
    print(f"[1/5] Read: {combined_path}")

    text, kept, removed = filter_images(text, book_dir, args.min_image_kb)
    print(f"[2/5] Images: kept={kept} removed={removed}")

    text = remove_ocr_noise(text)
    print("[3/5] OCR noise removed")

    text = fix_headings(text)
    print("[4/5] Headings fixed")

    text = common_cleanup(text)

    fixed_path = md_dir / f"{args.book}_fixed.md"
    fixed_path.write_text(text, encoding="utf-8")
    print(f"[5/5] Saved: {fixed_path}")

    # CSSは本ごとの paddle_output/{book}/ に保存
    css_path = book_dir / "epub_style.css"
    write_css(css_path)

    epub_path = epub_dir / f"{args.book}.epub"
    rc = build_epub(fixed_path, epub_path, css_path,
                    title, args.author, args.lang, book_dir)

    if rc == 0:
        print("\n========================================")
        print(f" EPUB created: {epub_path}")
        print("========================================")
    else:
        print(f"\n  Completed with warnings: {epub_path}")


if __name__ == "__main__":
    main()
