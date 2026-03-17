#!/usr/bin/env python3
"""
run.py
PDF → EPUB 変換をワンコマンドで実行する。
引数なしで実行すると対話形式で入力を求める。

Usage:
    python E:\\Books\\pdf2epub\\scripts\\run.py
    python E:\\Books\\pdf2epub\\scripts\\run.py --book 易经 --title "易经" --author "著者名"
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


def parse_args():
    p = argparse.ArgumentParser(description="PDF → EPUB 全工程一括実行")
    p.add_argument("--book",         default="",     help="本の名前（PDFファイル名と一致）")
    p.add_argument("--title",        default="",     help="EPUBのタイトル（省略時は bookと同じ）")
    p.add_argument("--author",       default="",     help="EPUBの著者名")
    p.add_argument("--lang",         default="zh-CN",help="言語コード")
    p.add_argument("--pdf",          default=r"E:\Books\pdf",           help="PDF元フォルダ")
    p.add_argument("--paddle",       default=r"E:\Books\paddle_output",  help="PaddleOCR出力ベースフォルダ")
    p.add_argument("--md",           default=r"E:\Books\pdf2epub\md",    help="MD保存先")
    p.add_argument("--epub",         default=r"E:\Books\epub",           help="EPUB保存先")
    p.add_argument("--min-image-kb", type=int, default=5)
    p.add_argument("--skip-ocr",     action="store_true", help="Step 1（OCR）をスキップ")
    return p.parse_args()


def prompt(args):
    """未入力の項目を対話形式で聞く"""
    print("\n========================================")
    print(" PDF → EPUB コンバーター")
    print("========================================")

    if not args.book:
        args.book = input("Book name : ").strip()
        if not args.book:
            print("ERROR: Book name is required.", file=sys.stderr)
            sys.exit(1)

    if not args.title:
        val = input(f"Title      [Enter = {args.book}]: ").strip()
        args.title = val or args.book

    if not args.author:
        args.author = input("Author     [Enter to skip]: ").strip()

    return args


def run(cmd: list, step: str):
    print(f"\n{'='*48}")
    print(f" {step}")
    print(f"{'='*48}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nERROR: {step} failed (exit code {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)


def main():
    args = parse_args()
    args = prompt(args)
    title = args.title or args.book

    # PDFを検索（サブフォルダも含めて探す）
    pdf_base = Path(args.pdf)
    pdf_path = None
    for candidate in pdf_base.rglob(f"{args.book}.pdf"):
        pdf_path = candidate
        break

    # Step 1: OCR
    if not args.skip_ocr:
        if pdf_path is None:
            print(f"ERROR: PDF not found: {args.book}.pdf under {pdf_base}", file=sys.stderr)
            sys.exit(1)
        save_path = str(Path(args.paddle) / args.book)
        run([
            "paddleocr", "pp_structurev3",
            "-i", str(pdf_path),
            "--use_doc_orientation_classify", "False",
            "--use_doc_unwarping", "False",
            "--use_formula_recognition", "False",
            "--save_path", save_path,
        ], "Step 1: OCR")

    # Step 2: 結合・クリーンアップ
    run([
        sys.executable, str(SCRIPTS_DIR / "clean_and_combine.py"),
        "--book",   args.book,
        "--paddle", args.paddle,
        "--md",     args.md,
    ], "Step 2: Combine & Cleanup")

    # Step 3: 整形・EPUB化
    cmd3 = [
        sys.executable, str(SCRIPTS_DIR / "fix_and_build.py"),
        "--book",         args.book,
        "--paddle",       args.paddle,
        "--md",           args.md,
        "--epub",         args.epub,
        "--title",        title,
        "--lang",         args.lang,
        "--min-image-kb", str(args.min_image_kb),
    ]
    if args.author:
        cmd3 += ["--author", args.author]
    run(cmd3, "Step 3: Fix & Build EPUB")

    print(f"\n{'='*48}")
    print(f" Done! -> {Path(args.epub) / (args.book + '.epub')}")
    print(f"{'='*48}")


if __name__ == "__main__":
    main()
