#!/usr/bin/env python3
"""
run.py
PDF → EPUB 全工程一括実行スクリプト。
引数なしで実行すると対話形式で入力を求める。

Steps:
  1. OCR    : PDF → paddle_output/{book}/_N.md
  2. Combine: _N.md → md/{book}_combined.md
  3. LLM Fix: _combined.md → md/{book}_llm_fixed.md  (Gemini API)
  4. EPUB   : _llm_fixed.md → epub/{book}.epub

Usage:
    python E:\\Books\\pdf2epub\\scripts\\run.py
    python E:\\Books\\pdf2epub\\scripts\\run.py --book 易经 --title "易经" --author "著者名"
    python E:\\Books\\pdf2epub\\scripts\\run.py --skip-ocr --skip-llm  # 辺期Stepのみ
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


def parse_args():
    p = argparse.ArgumentParser(description="PDF → EPUB 全工程")
    p.add_argument("--book",         default="")
    p.add_argument("--title",        default="")
    p.add_argument("--author",       default="")
    p.add_argument("--lang",         default="zh-CN")
    p.add_argument("--pdf",          default=r"E:\Books\pdf")
    p.add_argument("--paddle",       default=r"E:\Books\paddle_output")
    p.add_argument("--md",           default=r"E:\Books\pdf2epub\md")
    p.add_argument("--epub",         default=r"E:\Books\epub")
    p.add_argument("--min-image-kb", type=int, default=5)
    p.add_argument("--skip-ocr",     action="store_true", help="Step 1 をスキップ")
    p.add_argument("--skip-combine", action="store_true", help="Step 2 をスキップ")
    p.add_argument("--skip-llm",     action="store_true", help="Step 3 をスキップ")
    p.add_argument("--skip-epub",    action="store_true", help="Step 4 をスキップ")
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
        run_ocr(pdf_path, Path(args.paddle) / args.book)

    # Step 2: 結合・クリーンアップ
    if not args.skip_combine:
        run_cmd([
            sys.executable, str(SCRIPTS_DIR / "clean_and_combine.py"),
            "--book", args.book, "--paddle", args.paddle, "--md", args.md,
        ], "Step 2: Combine & Cleanup")

    # Step 3: LLM整形
    if not args.skip_llm:
        run_cmd([
            sys.executable, str(SCRIPTS_DIR / "llm_fix.py"),
            "--book", args.book, "--md", args.md,
        ], "Step 3: LLM Fix")

    # Step 4: EPUBビルド
    if not args.skip_epub:
        cmd4 = [
            sys.executable, str(SCRIPTS_DIR / "build_epub.py"),
            "--book",         args.book,
            "--paddle",       args.paddle,
            "--md",           args.md,
            "--epub",         args.epub,
            "--title",        title,
            "--lang",         args.lang,
            "--min-image-kb", str(args.min_image_kb),
        ]
        if args.author:
            cmd4 += ["--author", args.author]
        if args.skip_llm:
            cmd4 += ["--no-llm"]
        run_cmd(cmd4, "Step 4: Build EPUB")

    print(f"\n{'='*48}")
    print(f" Done! -> {Path(args.epub) / (args.book + '.epub')}")
    print(f"{'='*48}")


if __name__ == "__main__":
    main()
