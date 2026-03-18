#!/usr/bin/env python3
"""
build_epub.py
_llm_fixed.md （または _combined.md）から EPUB をビルドする。

Usage:
    python E:\\Books\\pdf2epub\\scripts\\build_epub.py --book 易经 --title "易经" --author "著者名"
"""

import argparse
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
    p = argparse.ArgumentParser(description="MD → EPUB ビルド")
    p.add_argument("--book",         required=True)
    p.add_argument("--paddle",       default=r"E:\Books\paddle_output")
    p.add_argument("--md",           default=r"E:\Books\pdf2epub\md")
    p.add_argument("--epub",         default=r"E:\Books\epub")
    p.add_argument("--title",        default="")
    p.add_argument("--author",       default="")
    p.add_argument("--lang",         default="zh-CN")
    p.add_argument("--min-image-kb", type=int, default=5)
    p.add_argument("--no-llm",       action="store_true", help="_combined.mdを使用（LLM整形なし）")
    return p.parse_args()


def filter_images(text: str, book_dir: Path, min_kb: int) -> tuple[str, int, int]:
    import re
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


def main():
    args = parse_args()
    book_dir = Path(args.paddle) / args.book
    md_dir   = Path(args.md)
    epub_dir = Path(args.epub)
    epub_dir.mkdir(parents=True, exist_ok=True)
    title = args.title or args.book

    # 入力 MD の優先順位: _llm_fixed.md > _combined.md
    if args.no_llm:
        md_path = md_dir / f"{args.book}_combined.md"
    else:
        md_path = md_dir / f"{args.book}_llm_fixed.md"
        if not md_path.exists():
            print(f"WARNING: _llm_fixed.md not found, falling back to _combined.md")
            md_path = md_dir / f"{args.book}_combined.md"

    if not md_path.exists():
        print(f"ERROR: not found -> {md_path}", file=sys.stderr)
        sys.exit(1)

    print("========================================")
    print(f" Build EPUB: {title}")
    print(f" Input: {md_path.name}")
    print("========================================")

    text = md_path.read_text(encoding="utf-8")
    text, kept, removed = filter_images(text, book_dir, args.min_image_kb)
    print(f"Images: kept={kept} removed={removed}")

    # CSSは本ごとの paddle_outputフォルダに保存
    css_path = book_dir / "epub_style.css"
    css_path.write_text(EPUB_CSS, encoding="utf-8")

    epub_path = epub_dir / f"{args.book}.epub"
    cmd = [
        "pandoc", str(md_path), "-o", str(epub_path),
        "--metadata", f"title={title}",
        "--metadata", f"lang={args.lang}",
        "-f", "markdown", "-t", "epub3",
        f"--css={css_path}",
        f"--resource-path={book_dir}",
        "--epub-chapter-level=1",
        "--toc", "--toc-depth=2",
    ]
    if args.author:
        cmd += ["--metadata", f"author={args.author}"]

    result = subprocess.run(cmd)
    if result.returncode == 0:
        print(f"\n========================================")
        print(f" EPUB created: {epub_path}")
        print(f"========================================")
    else:
        print(f"Completed with warnings: {epub_path}")


if __name__ == "__main__":
    main()
