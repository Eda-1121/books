#!/usr/bin/env python3
"""
pdf_to_md.py
PDFをページ番号順に画像化し、Gemini Vision APIで直接MDを生成する。

Dependencies:
    pip install pymupdf google-genai python-dotenv

Usage:
    python E:\\Books\\pdf2epub\\scripts\\pdf_to_md.py --book 易经
    python E:\\Books\\pdf2epub\\scripts\\pdf_to_md.py --book 易经 --start 1 --end 10
    python E:\\Books\\pdf2epub\\scripts\\pdf_to_md.py --book 易经 --resume
"""

import argparse
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
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: google-genai not installed. Run: pip install google-genai", file=sys.stderr)
    sys.exit(1)

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

RETRY_WAIT = 15
PAGE_WAIT  = 2
DPI        = 150


def parse_args():
    p = argparse.ArgumentParser(description="PDF → MD (Gemini Vision)")
    p.add_argument("--book",   required=True)
    p.add_argument("--pdf",    default=r"E:\Books\pdf")
    p.add_argument("--md",     default=r"E:\Books\pdf2epub\md")
    p.add_argument("--model",  default="gemini-2.0-flash")
    p.add_argument("--start",  type=int, default=1)
    p.add_argument("--end",    type=int, default=None)
    p.add_argument("--dpi",    type=int, default=DPI)
    p.add_argument("--resume", action="store_true")
    return p.parse_args()


def find_pdf(pdf_base: Path, book: str) -> Path:
    for candidate in pdf_base.rglob(f"{book}.pdf"):
        return candidate
    return None


def page_to_bytes(page, dpi: int) -> bytes:
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes("png")


def process_page(client, model: str, page, page_num: int, total: int, dpi: int) -> str:
    img_bytes = page_to_bytes(page, dpi)
    contents = types.Content(
        role="user",
        parts=[
            types.Part(text=PAGE_PROMPT),
            types.Part(
                inline_data=types.Blob(mime_type="image/png", data=img_bytes)
            ),
        ],
    )
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
            )
            print(f"  p.{page_num}/{total} done")
            return response.text
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "RESOURCE_EXHAUSTED" in err:
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

    client = genai.Client(api_key=api_key)

    page_dir = md_dir / f"{args.book}_pages"
    page_dir.mkdir(exist_ok=True)

    parts = []
    for page_num in range(start, end + 1):
        page_file = page_dir / f"{page_num:04d}.md"
        if args.resume and page_file.exists():
            parts.append(page_file.read_text(encoding="utf-8"))
            print(f"  p.{page_num}/{end} (cached)")
            continue
        page = doc[page_num - 1]
        text = process_page(client, args.model, page, page_num, end, args.dpi)
        page_file.write_text(text, encoding="utf-8")
        parts.append(text)
        time.sleep(PAGE_WAIT)

    doc.close()

    out_path = md_dir / f"{args.book}_vision.md"
    out_path.write_text("\n\n---\n\n".join(parts), encoding="utf-8")
    print(f"\nSaved: {out_path}")
    print(f"Page cache: {page_dir}")


if __name__ == "__main__":
    main()
