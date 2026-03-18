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
    p.add_argument("--book",         default="",     help="本の名前")
    p.add_argument("--title",        default="",     help="EPUBのタイトル")
    p.add_argument("--author",       default="",     help="EPUBの著者名")
    p.add_argument("--lang",         default="zh-CN",help="言語コード")
    p.add_argument("--pdf",          default=r"E:\Books\pdf")
    p.add_argument("--paddle",       default=r"E:\Books\paddle_output")
    p.add_argument("--md",           default=r"E:\Books\pdf2epub\md")
    p.add_argument("--epub",         default=r"E:\Books\epub")
    p.add_argument("--min-image-kb", type=int, default=5)
    p.add_argument("--skip-ocr",     action="store_true", help="Step 1（OCR）をスキップ")
    return p.parse_args()


def prompt(args):
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


def run_ocr(pdf_path: Path, save_dir: Path):
    """PaddleOCR Python APIでOCRし、MDと画像のみを保存する"""
    print("\n================================================")
    print(" Step 1: OCR")
    print("================================================")
    try:
        from paddleocr import PPStructureV3
    except ImportError:
        print("ERROR: paddleocr is not installed.", file=sys.stderr)
        sys.exit(1)

    save_dir.mkdir(parents=True, exist_ok=True)
    pipeline = PPStructureV3(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_formula_recognition=False,
    )
    output = pipeline.predict(input=str(pdf_path))
    for res in output:
        res.save_to_markdown(save_path=str(save_dir))
    print(f"OCR complete -> {save_dir}")


def run_cmd(cmd: list, step: str):
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

    # Step 1: OCR
    if not args.skip_ocr:
        pdf_base = Path(args.pdf)
        pdf_path = None
        for candidate in pdf_base.rglob(f"{args.book}.pdf"):
            pdf_path = candidate
            break
        if pdf_path is None:
            print(f"ERROR: PDF not found: {args.book}.pdf under {pdf_base}", file=sys.stderr)
            sys.exit(1)
        save_dir = Path(args.paddle) / args.book
        run_ocr(pdf_path, save_dir)

    # Step 2: 結合・クリーンアップ
    run_cmd([
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
    run_cmd(cmd3, "Step 3: Fix & Build EPUB")

    print(f"\n{'='*48}")
    print(f" Done! -> {Path(args.epub) / (args.book + '.epub')}")
    print(f"{'='*48}")


if __name__ == "__main__":
    main()
