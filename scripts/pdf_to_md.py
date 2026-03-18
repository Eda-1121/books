#!/usr/bin/env python3
"""
pdf_to_md.py
PDFをMDに変換する。画像PDF / テキストPDFを自動判定し、モードを切り替えられる。

Dependencies:
    pip install pymupdf google-genai python-dotenv

Usage:
    # 自動判定（おすすめ）
    python pdf_to_md.py --book 易经

    # 強制画像OCR（Vision）
    python pdf_to_md.py --book 易经 --mode vision

    # 強制テキスト抽出（OCRなし）
    python pdf_to_md.py --book 易经 --mode text

    # LLM整形も一気に実行
    python pdf_to_md.py --book 易经 --llm-fix

    # 途中から再開
    python pdf_to_md.py --book 易经 --resume
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
    import fitz
except ImportError:
    print("ERROR: pymupdf not installed. Run: pip install pymupdf", file=sys.stderr)
    sys.exit(1)

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)

# ---- 定数 ---------------------------------------------------------------

TEXT_THRESHOLD   = 50    # 1ページの文字数がこれ以下なら画像PDFと判定

PAGE_WAIT        = 2     # Visionリクエスト間隔（秒）
RETRY_WAIT       = 15    # レートリミット待機秒
DPI              = 150

CHUNK_CHARS      = 12000 # LLM整形のチャンクサイズ

VISION_PROMPT = """このページの内容をMarkdown形式で正確に書き起こしてください。
ルール：
1. 章・節の見出しは # または ## を使用する
2. 段落の改行と文章構造を正確に再現する
3. 表は Markdown 表形式に変換する
4. 箇条書きは - または 1. を使用する
5. ページ番号やヘッダー・フッターは除外する
6. 画像がある場合は [image] と記載する
7. Markdownテキストのみ出力する（説明文不要）
"""

LLM_FIX_PROMPT = """以下のMarkdownテキストを整形してください。
ルール：
1. 内容は一切変えず、レイアウトと構造のみ修正する
2. 第N章・第N節などの章節見出しは # または ## に変換する
3. OCRノイズ（意味のない記号、孤立文字）を削除する
4. 不自然な改行を修正して文章を自然な流れにする
5. 表・箇条書きは正しいMarkdown構文に変換する
6. Markdown形式のみ出力（説明文不要）
"""

# ---- 小機能 -------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="PDF → MD（自動判定 / Vision / テキスト）")
    p.add_argument("--book",     required=True,  help="本のタイトル（PDFファイル名）")
    p.add_argument("--pdf",      default=r"E:\Books\pdf", help="PDFフォルダ")
    p.add_argument("--md",       default=r"E:\Books\pdf2epub\md", help="出力フォルダ")
    p.add_argument("--mode",     default="auto",  choices=["auto", "vision", "text"],
                   help="auto:自動判定 / vision:画像OCR強制 / text:テキスト抽出強制")
    p.add_argument("--model",    default="gemini-2.5-flash", help="Geminiモデル")
    p.add_argument("--start",    type=int, default=1)
    p.add_argument("--end",      type=int, default=None)
    p.add_argument("--dpi",      type=int, default=DPI)
    p.add_argument("--resume",   action="store_true", help="ページキャッシュから再開")
    p.add_argument("--llm-fix",  action="store_true", help="MD出力後にLLMで整形も実行")
    p.add_argument("--threshold", type=int, default=TEXT_THRESHOLD,
                   help="テキストPDF判定の文字数閾値（デフォルト:50）")
    return p.parse_args()


def find_pdf(pdf_base: Path, book: str) -> Path:
    for candidate in pdf_base.rglob(f"{book}.pdf"):
        return candidate
    return None


def detect_pdf_type(doc, sample_pages: int = 5, threshold: int = TEXT_THRESHOLD) -> str:
    """
    先頭sample_pagesページの文字数を調べ、平均がthreshold以上なら'text'、未満なら'vision'を返す。
    """
    pages_to_check = min(sample_pages, len(doc))
    total_chars = 0
    for i in range(pages_to_check):
        text = doc[i].get_text("text").strip()
        total_chars += len(text)
    avg = total_chars / pages_to_check
    pdf_type = "text" if avg >= threshold else "vision"
    print(f" 判定: 1ページ平均{avg:.0f}文字 → {'\u30c6\u30ad\u30b9\u30c8PDF' if pdf_type == 'text' else '\u753b\u50cfPDF (Visionモード)'} ")
    return pdf_type


# ---- テキスト抽出モード ---------------------------------------------------------

def extract_text_page(page) -> str:
    """テキストPDFからページテキストを抽出し、簡単なMarkdown形式に整形する。"""
    blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
    lines = []
    for b in sorted(blocks, key=lambda b: (b[1], b[0])):  # y座標順
        if b[6] != 0:  # 0=テキスト、1=画像
            lines.append("[image]")
            continue
        text = b[4].strip()
        if not text:
            continue
        lines.append(text)
    return "\n\n".join(lines)


# ---- Visionモード -----------------------------------------------------------

def page_to_bytes(page, dpi: int) -> bytes:
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes("png")


def extract_text_from_response(response) -> str:
    if response.text is not None:
        return response.text
    try:
        parts = response.candidates[0].content.parts
        return "\n".join(p.text for p in parts if hasattr(p, "text") and p.text)
    except Exception:
        return ""


def process_vision_page(client, model: str, page, page_num: int, total: int, dpi: int) -> str:
    img_bytes = page_to_bytes(page, dpi)
    contents = types.Content(
        role="user",
        parts=[
            types.Part(text=VISION_PROMPT),
            types.Part(inline_data=types.Blob(mime_type="image/png", data=img_bytes)),
        ],
    )
    for attempt in range(4):
        try:
            response = client.models.generate_content(model=model, contents=contents)
            print(f"  p.{page_num}/{total} done [vision]")
            return extract_text_from_response(response)
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


# ---- LLM整形 -------------------------------------------------------------

def split_chunks(text: str, max_chars: int) -> list:
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current += ("\n\n" if current else "") + para
    if current:
        chunks.append(current.strip())
    return chunks


def llm_fix(client, model: str, text: str) -> str:
    chunks = split_chunks(text, CHUNK_CHARS)
    fixed = []
    print(f"\n LLM整形開始 ({len(chunks)}チャンク)...")
    for i, chunk in enumerate(chunks):
        prompt = f"{LLM_FIX_PROMPT}\n\n---\n\n{chunk}"
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)]
                    )
                )
                fixed.append(extract_text_from_response(response) or chunk)
                print(f"  chunk {i+1}/{len(chunks)} done")
                break
            except Exception as e:
                err = str(e)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    print(f"  rate limit, waiting {RETRY_WAIT}s...")
                    time.sleep(RETRY_WAIT)
                else:
                    print(f"  LLM ERROR: {e}", file=sys.stderr)
                    fixed.append(chunk)
                    break
        time.sleep(1)
    return "\n\n".join(fixed)


# ---- メイン ---------------------------------------------------------------

def main():
    args = parse_args()
    md_dir = Path(args.md)
    md_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = find_pdf(Path(args.pdf), args.book)
    if pdf_path is None:
        print(f"ERROR: {args.book}.pdf not found under {args.pdf}", file=sys.stderr)
        sys.exit(1)

    doc   = fitz.open(str(pdf_path))
    total = len(doc)
    start = max(1, args.start)
    end   = min(total, args.end) if args.end else total

    # ---- PDFタイプ判定 ----
    if args.mode == "auto":
        mode = detect_pdf_type(doc, threshold=args.threshold)
    else:
        mode = args.mode

    # Visionモードの場合はAPIクライアントが必要
    client = None
    if mode == "vision" or args.llm_fix:
        if genai is None:
            print("ERROR: google-genai not installed. Run: pip install google-genai", file=sys.stderr)
            sys.exit(1)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print(f"ERROR: GEMINI_API_KEY not set. Check {ENV_PATH}", file=sys.stderr)
            sys.exit(1)
        client = genai.Client(api_key=api_key)

    print(f"\n========================================")
    print(f" PDF → MD")
    print(f" Book : {args.book}")
    print(f" PDF  : {pdf_path}")
    print(f" Pages: {start} - {end} / {total}")
    print(f" Mode : {mode.upper()}")
    print(f" LLM整形: {'ON (' + args.model + ')' if args.llm_fix else 'OFF'}")
    print(f"========================================")

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

        if mode == "vision":
            text = process_vision_page(client, args.model, page, page_num, end, args.dpi)
        else:
            text = extract_text_page(page)
            print(f"  p.{page_num}/{end} done [text]")

        page_file.write_text(text, encoding="utf-8")
        parts.append(text)

        if mode == "vision":
            time.sleep(PAGE_WAIT)

    doc.close()

    combined = "\n\n---\n\n".join(parts)

    # LLM整形
    if args.llm_fix:
        combined = llm_fix(client, args.model, combined)
        out_path = md_dir / f"{args.book}_llm_fixed.md"
    else:
        out_path = md_dir / f"{args.book}_vision.md"

    out_path.write_text(combined, encoding="utf-8")
    print(f"\nSaved: {out_path}")
    print(f"Page cache: {page_dir}")


if __name__ == "__main__":
    main()
