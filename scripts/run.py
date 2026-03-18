#!/usr/bin/env python3
"""
run.py
PDF → EPUB 全工程一括実行。自動判定・モード選択対応。

モード：
  auto   ：PDFを自動判定（テキストPDF / 画像PDF）
  vision ：Gemini Vision OCR → MD → EPUB
  text   ：PaddleOCR → MD → EPUB（従来の方法）

Usage:
    python run.py
    python run.py --book 易经 --title "易经" --author "著者名" --mode auto
    python run.py --book 易经 --mode vision --llm-fix
    python run.py --book 易经 --mode text --skip-llm
    python run.py --book 易经 --skip-ocr --skip-epub  # MD生成のみ
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


def parse_args():
    p = argparse.ArgumentParser(description="PDF → EPUB 全工程")
    p.add_argument("--book",          default="")
    p.add_argument("--title",         default="")
    p.add_argument("--author",        default="")
    p.add_argument("--lang",          default="zh-CN")
    p.add_argument("--pdf",           default=r"E:\Books\pdf")
    p.add_argument("--paddle",        default=r"E:\Books\paddle_output")
    p.add_argument("--md",            default=r"E:\Books\pdf2epub\md")
    p.add_argument("--epub",          default=r"E:\Books\epub")
    p.add_argument("--min-image-kb",  type=int, default=5)
    p.add_argument("--mode",          default="auto", choices=["auto", "vision", "text"],
                   help="auto:自動判定 / vision:Gemini Vision / text:PaddleOCR")
    p.add_argument("--llm-fix",       action="store_true",
                   help="MD出力後にLLM整形を実行（vision/autoモードのみ有効）")
    p.add_argument("--model",         default="gemini-2.5-flash", help="Geminiモデル")
    p.add_argument("--skip-ocr",      action="store_true", help="Step 1（OCR/Vision）をスキップ")
    p.add_argument("--skip-combine",  action="store_true", help="Step 2（結合）をスキップ（textモードのみ）")
    p.add_argument("--skip-llm",      action="store_true", help="Step 3（LLM整形）をスキップ")
    p.add_argument("--skip-epub",     action="store_true", help="Step 4（EPUBビルド）をスキップ")
    p.add_argument("--resume",        action="store_true", help="ページキャッシュから再開（vision/autoモード）")
    p.add_argument("--threshold",     type=int, default=50,
                   help="テキストPDF判定閾値（デフォルト:50文字）")
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


def find_pdf(pdf_base: Path, book: str) -> Path:
    for candidate in pdf_base.rglob(f"{book}.pdf"):
        return candidate
    return None


def detect_pdf_type(pdf_path: Path, threshold: int = 50) -> str:
    """PDFの先頭5ページの文字数でテキストPDF/画像PDFを判定する。"""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        pages = min(5, len(doc))
        total = sum(len(doc[i].get_text("text").strip()) for i in range(pages))
        doc.close()
        avg = total / pages
        pdf_type = "text" if avg >= threshold else "vision"
        print(f" 判定: 1ページ平均{avg:.0f}文字 → {'\u30c6\u30ad\u30b9\u30c8PDF' if pdf_type == 'text' else '\u753b像PDF (Visionモード)'} ")
        return pdf_type
    except Exception as e:
        print(f" 判定失敗: {e} → visionモードにフォールバック")
        return "vision"


def run_paddle_ocr(pdf_path: Path, save_dir: Path):
    print("\n================================================")
    print(" Step 1: PaddleOCR")
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

    # PDFパスを先に解決（判定やOCRで必要）
    pdf_path = find_pdf(Path(args.pdf), args.book)

    # ---- モード自動判定 ----
    mode = args.mode
    if mode == "auto":
        if pdf_path is None:
            print("WARNING: PDF not found for auto-detect, defaulting to vision mode")
            mode = "vision"
        else:
            mode = detect_pdf_type(pdf_path, args.threshold)

    print(f"\n Mode: {mode.upper()}  LLM整形: {'ON' if (args.llm_fix or not args.skip_llm) else 'OFF'}")

    # ====================================================
    # モード A: vision / auto→vision
    # フロー: pdf_to_md.py (画像OCR) → [必要なら llm_fix] → build_epub.py
    # ====================================================
    if mode == "vision":
        if not args.skip_ocr:
            if pdf_path is None:
                print(f"ERROR: PDF not found: {args.book}.pdf", file=sys.stderr)
                sys.exit(1)
            cmd1 = [
                sys.executable, str(SCRIPTS_DIR / "pdf_to_md.py"),
                "--book",  args.book,
                "--pdf",   args.pdf,
                "--md",    args.md,
                "--mode",  "vision",
                "--model", args.model,
            ]
            if args.resume:
                cmd1 += ["--resume"]
            if args.llm_fix and not args.skip_llm:
                cmd1 += ["--llm-fix"]
            run_cmd(cmd1, "Step 1+3: Vision OCR [必要なら LLM整形]")

        if not args.skip_epub:
            cmd4 = [
                sys.executable, str(SCRIPTS_DIR / "build_epub.py"),
                "--book",         args.book,
                "--md",           args.md,
                "--epub",         args.epub,
                "--title",        title,
                "--lang",         args.lang,
                "--min-image-kb", str(args.min_image_kb),
                "--source",       "vision",
            ]
            if args.author:
                cmd4 += ["--author", args.author]
            if args.llm_fix and not args.skip_llm:
                cmd4 += ["--use-llm"]
            run_cmd(cmd4, "Step 4: Build EPUB")

    # ====================================================
    # モード B: text / auto→text
    # フロー: pdf_to_md.py (テキスト抽出) OR PaddleOCR → combine → [必要なら llm_fix] → build_epub.py
    # ====================================================
    else:  # text
        if not args.skip_ocr:
            if pdf_path is None:
                print(f"ERROR: PDF not found: {args.book}.pdf", file=sys.stderr)
                sys.exit(1)
            # テキストPDFはpdf_to_md.pyの--mode textで直接抽出
            cmd1 = [
                sys.executable, str(SCRIPTS_DIR / "pdf_to_md.py"),
                "--book",  args.book,
                "--pdf",   args.pdf,
                "--md",    args.md,
                "--mode",  "text",
            ]
            run_cmd(cmd1, "Step 1: Text Extraction")

        # Step 2: combine (textモードは_vision.mdに直接出力されるのでスキップ可能)
        # 旧来のPaddleOCRフロー用にkeep
        if not args.skip_combine:
            paddle_dir = Path(args.paddle) / args.book
            if paddle_dir.exists():
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
                "--source",       "text",
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
