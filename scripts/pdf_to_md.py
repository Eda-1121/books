#!/usr/bin/env python3
"""
pdf_to_md.py
PDFをページ番号順に画像化し、Gemini Vision APIで直接MDを生成する。
PaddleOCRは不要。

Dependencies:
    pip install pymupdf google-generativeai python-dotenv

Usage:
    python E:\\Books\\pdf2epub\\scripts\\pdf_to_md.py --book 易经
    python E:\\Books\\pdf2epub\\scripts\\pdf_to_md.py --book 易经 --start 1 --end 50
"""

import argparse
import base64
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv", file=sys.stderr)
    sys.exit(1)

try:
    import fitz  # pymupdf
except ImportError:
    print("ERROR: pymupdf not installed. Run: pip install pymupdf", file=sys.stderr)
    sys.exit(1)

try:
    import google.generativeai as genai
except ImportError:
    print("ERROR: google-generativeai not installed. Run: pip install google-generativeai", file=sys.stderr)
    sys.exit(1)

# .env を scripts/ フォルダから読み込む
ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)

PAGE_PROMPT = """このページの内容をMarkdown形式で正確に書き起こしてください。

ルール：
1. 章・節の見出しは # または ## を使用する
2. 段落の改行と文章構造を正確に再現する
3. 表は Markdown 表形式に変換する
4. 箇条書きは - または 1. を使用する
5. ページ番号やヘッダー・フッターは除外する
6. 画像がある場合は [image] と記載する
7. Markdownテキストのみ出力する（説明文不要）
"""

RETRY_WAIT = 15   # レートリミット時の待機秒数
PAGE_WAIT  = 2    # ページ間のインターバル（秒）
DPI        = 150  # 画像解像度（高いほど精度上がるが遅い）


def parse_args():
    p = argparse.ArgumentParser(description="PDF → MD (Gemini Vision)")
    p.add_argument("--book",  required=True,  help="本の名前")
    p.add_argument("--pdf",   default=r"E:\Books\pdf",          help="PDF元フォルダ")
    p.add_argument("--md",    default=r"E:\Books\pdf2epub\md",  help="MD保存先")
    p.add_argument("--model", default="gemini-2.0-flash",       help="使用モデル")
    p.add_argument("--start", type=int, default=1,              help="開始ページ（1始まり）")
    p.add_argument("--end",   type=int, default=None,           help="終了ページ（省略時は最後まで）")
    p.add_argument("--dpi",   type=int, default=DPI,            help="画像解像度")
    p.add_argument("--resume",action="store_true",              help="途中から再開（処理済ページをスキップ）")
    return p.parse_args()


def find_pdf(pdf_base: Path, book: str) -> Path:
    for candidate in pdf_base.rglob(f"{book}.pdf"):
        return candidate
    return None


def page_to_base64(page, dpi: int) -> str:
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    return base64.b64encode(pix.tobytes("png")).decode()


def process_page(model, page, page_num: int, total: int, dpi: int) -> str:
    img_b64 = page_to_base64(page, dpi)
    img_part = {"mime_type": "image/png", "data": img_b64}
    for attempt in range(4):
        try:
            response = model.generate_content([PAGE_PROMPT, img_part])
            print(f"  p.{page_num}/{total} done")
            return response.text
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "Resource" in err:
                wait = RETRY_WAIT * (attempt + 1)
                print(f"  p.{page_num} rate limit, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  p.{page_num} ERROR: {e}", file=sys.stderr)
                return f"<!-- page {page_num} error: {e} -->"
    return f"<!-- page {page_num} failed after retries -->"


def main():
    args = parse_args()
    md_dir = Path(args.md)
    md_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"ERROR: GEMINI_API_KEY not set. Check {ENV_PATH}", file=sys.stderr)
        sys.exit(1)

    pdf_path = find_pdf(Path(args.pdf), args.book)
    if pdf_path is None:
        print(f"ERROR: {args.book}.pdf not found under {args.pdf}", file=sys.stderr)
        sys.exit(1)

    doc   = fitz.open(str(pdf_path))
    total = len(doc)
    start = max(1, args.start)
    end   = min(total, args.end) if args.end else total

    print(f"\n========================================")
    print(f" PDF → MD (Gemini Vision)")
    print(f" Book : {args.book}")
    print(f" PDF  : {pdf_path}")
    print(f" Pages: {start} - {end} / {total}")
    print(f" Model: {args.model}")
    print(f"========================================")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(args.model)

    out_path   = md_dir / f"{args.book}_vision.md"
    page_dir   = md_dir / f"{args.book}_pages"   # ページ別MDのキャッシュ
    page_dir.mkdir(exist_ok=True)

    parts = []
    for page_num in range(start, end + 1):
        page_file = page_dir / f"{page_num:04d}.md"

        # --resume: 処理済ファイルはスキップ
        if args.resume and page_file.exists():
            parts.append(page_file.read_text(encoding="utf-8"))
            print(f"  p.{page_num}/{end} (cached)")
            continue

        page = doc[page_num - 1]
        text = process_page(model, page, page_num, end, args.dpi)
        page_file.write_text(text, encoding="utf-8")  # キャッシュ保存
        parts.append(text)
        time.sleep(PAGE_WAIT)

    doc.close()

    out_path.write_text("\n\n---\n\n".join(parts), encoding="utf-8")
    print(f"\nSaved: {out_path}")
    print(f"Page cache: {page_dir}")


if __name__ == "__main__":
    main()
