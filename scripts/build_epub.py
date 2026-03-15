#!/usr/bin/env python3
"""
build_epub.py
既存の整形済み Markdown (_fixed.md または任意) から EPUB だけを生成する薄いラッパー。

Usage:
    python scripts/build_epub.py --book 影响力
    python scripts/build_epub.py --book 影响力 --title "影响力" --author "[美]罗伯特·西奥迪尼"
    python scripts/build_epub.py --book 影响力 --md E:\\Books\\paddle_output\\影响力_fixed.md
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
    p = argparse.ArgumentParser(description="Build EPUB from fixed Markdown")
    p.add_argument("--book",   required=True)
    p.add_argument("--paddle", default=r"E:\Books\paddle_output")
    p.add_argument("--epub",   default=r"E:\Books\epub")
    p.add_argument("--md",     default="",  help="Override input markdown path")
    p.add_argument("--title",  default="")
    p.add_argument("--author", default="")
    p.add_argument("--lang",   default="zh-CN")
    return p.parse_args()


def main():
    args = parse_args()
    paddle_dir = Path(args.paddle)
    epub_dir   = Path(args.epub)
    epub_dir.mkdir(parents=True, exist_ok=True)
    title = args.title or args.book

    md_path = Path(args.md) if args.md else paddle_dir / f"{args.book}_fixed.md"
    if not md_path.exists():
        print(f"ERROR: not found -> {md_path}", file=sys.stderr)
        sys.exit(1)

    css_path = paddle_dir / "epub_style.css"
    css_path.write_text(EPUB_CSS, encoding="utf-8")

    epub_path = epub_dir / f"{args.book}.epub"

    cmd = [
        "pandoc", str(md_path), "-o", str(epub_path),
        "--metadata", f"title={title}",
        "--metadata", f"lang={args.lang}",
        "-f", "markdown", "-t", "epub3",
        f"--css={css_path}",
        f"--resource-path={paddle_dir}",
        "--epub-chapter-level=1",
        "--toc", "--toc-depth=2",
    ]
    if args.author:
        cmd += ["--metadata", f"author={args.author}"]

    print(f"Building EPUB: {epub_path}")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print(f"\nEPUB created: {epub_path}")
    else:
        print(f"\nCompleted with warnings: {epub_path}")


if __name__ == "__main__":
    main()
