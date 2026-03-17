#!/usr/bin/env python3
"""
clean_and_combine.py
OCR出力の個別Markdownファイルを結合して {BookName}_combined.md を生成する。
不要ファイル（.docx / .tex / _res.json / デバッグPNG）も自動削除する。

Usage:
    python scripts/clean_and_combine.py --book 易经
    python scripts/clean_and_combine.py --book 易经 --paddle E:\\Books\\paddle_output --epub E:\\Books\\epub
"""

import argparse
import re
import sys
from pathlib import Path

JUNK_PATTERNS = [
    "*.docx",
    "*.tex",
    "*_res.json",
    "*_layout_det_res.png",
    "*_layout_order_res.png",
    "*_overall_ocr_res.png",
    "*_preprocessed_img.png",
    "*_region_det_res.png",
]


def parse_args():
    p = argparse.ArgumentParser(description="Combine OCR Markdown pages")
    p.add_argument("--book",   required=True, help="Book name (e.g. 易经)")
    p.add_argument("--paddle", default=r"E:\Books\paddle_output", help="PaddleOCR output directory")
    p.add_argument("--epub",   default=r"E:\Books\epub",          help="EPUB output directory")
    return p.parse_args()


def cleanup_junk(paddle_dir: Path):
    """PaddleOCRが生成する不要ファイルを削除"""
    removed = 0
    for pattern in JUNK_PATTERNS:
        for f in paddle_dir.glob(pattern):
            f.unlink()
            removed += 1
    print(f"Cleaned up {removed} junk files")


def filter_images(text: str, paddle_dir: Path) -> str:
    """存在しない画像の参照を削除する"""
    def check_div_img(m):
        img_path = paddle_dir / m.group(1)
        return m.group(0) if img_path.exists() else ""

    def check_md_img(m):
        img_path = paddle_dir / m.group(1)
        return m.group(0) if img_path.exists() else ""

    text = re.sub(r'<div[^>]*><img\s+src="([^"]*)"[^>]*></div>', check_div_img, text)
    text = re.sub(r'!\[[^\]]*\]\(([^)]*)\)', check_md_img, text)
    return text


def main():
    args = parse_args()
    paddle_dir = Path(args.paddle)
    epub_dir   = Path(args.epub)
    epub_dir.mkdir(parents=True, exist_ok=True)

    # ページ番号順にソート: {BookName}_1.md, {BookName}_2.md ...
    pattern = re.compile(rf"^{re.escape(args.book)}_(\d+)\.md$")
    md_files = sorted(
        [f for f in paddle_dir.iterdir()
         if f.is_file() and pattern.match(f.name)],
        key=lambda f: int(pattern.match(f.name).group(1))
    )

    if not md_files:
        print(f"ERROR: No markdown files found for '{args.book}' in {paddle_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(md_files)} pages")

    parts = []
    for f in md_files:
        text = f.read_text(encoding="utf-8")
        text = filter_images(text, paddle_dir)
        parts.append(text)

    combined = "\n\n".join(parts)
    out_path = paddle_dir / f"{args.book}_combined.md"
    out_path.write_text(combined, encoding="utf-8")
    print(f"Combined MD: {out_path}")

    # 不要ファイルを削除
    cleanup_junk(paddle_dir)


if __name__ == "__main__":
    main()
