#!/usr/bin/env python3
"""
llm_fix.py
OCR済みMDをGemini APIで「構造専用」に整形し、_llm_fixed.mdを生成する。
チャンクサイズを小さく抑え、無料LLM枠で　1日5冊分処理できるように設計する。

Dependencies:
    pip install google-genai python-dotenv

Usage:
    python llm_fix.py --book 易经
    python llm_fix.py --book 易经 --chunk-chars 7000
    python llm_fix.py --book 易经 --input-md E:\\Books\\pdf2epub\\md\\custom.md
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
    from google import genai
except ImportError:
    print("ERROR: google-genai not installed. Run: pip install google-genai", file=sys.stderr)
    sys.exit(1)

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)

# 無料LLM枠に当たるため、小さめに划ったチャンクサイズ。
# 1冊 ≈7000文字 × 10チャンク = 約 70k文字/冊、1日5冊 = 50チャンク前後
CHUNK_CHARS = 7000
RETRY_WAIT  = 15   # レートリミット時の待機秒
CHUNK_WAIT  = 2    # チャンク間隔（日常的に無料枠を超えないため）

# 構造専用・内容変更禁止のプロンプト
SYSTEM_PROMPT = """\
あなたは書籍の編集者です。
OCRで取得したMarkdownテキストを「レイアウトと構造のみ」整えるタスクを行います。

絶対に守るルール：
1. 内容を一切変えない。文字の修正・要約・削除・追記は絶対禁止。
2. 誤字・脱字の修正もしない。原文の文字はそのまま残す。
3. 第N章・第N節などの章節見出しは # または ## に変換する。
4. 不自然な改行を修正し、文章を自然な段落にする。
5. 箇条書きは - または 1. のMarkdownリストにする。
6. 表は可能な限りMarkdown表に変換する。
7. 脆注（ページ下部の番号付き短い文）は Markdown脆注構文に変換する：
   - 本文側の番号→ 「文字[^1]」の形式
   - 脆注内容→ 文末に「[^1]: 注釈内容」の形式
   - 脆注の内容は絶対に削除・要約しない。
8. 画像参照（![...](...)  や [image]）はそのまま保持する。
9. 出力はMarkdown形式のみ。説明文・前置きは一切書かない。
"""


def parse_args():
    p = argparse.ArgumentParser(description="LLMでMDを構造整形（無料枠1日5冊対応）")
    p.add_argument("--book",        required=True, help="本のタイトル")
    p.add_argument("--md",          default=r"E:\Books\pdf2epub\md")
    p.add_argument("--model",       default="gemini-2.0-flash")
    p.add_argument("--chunk-chars", type=int, default=CHUNK_CHARS,
                   help=f"チャンクサイズ（デフォルト: {CHUNK_CHARS}文字）")
    p.add_argument("--input-md",    default=None,
                   help="入力MDファイルを直接指定（省略時は自動選択）")
    return p.parse_args()


def resolve_input_md(md_dir: Path, book: str) -> Path:
    """
    入力MDの自動選択優先順位：
    _combined.md → _vision.md
    """
    for name in [f"{book}_combined.md", f"{book}_vision.md"]:
        p = md_dir / name
        if p.exists():
            return p
    return md_dir / f"{book}_combined.md"  # 存在しなくてもエラーは後で出たせる


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


def fix_chunk(client, model: str, chunk: str, idx: int, total: int) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\n---\n\n{chunk}"
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            print(f"  chunk {idx+1}/{total} done")
            return response.text or chunk
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "RESOURCE_EXHAUSTED" in err:
                wait = RETRY_WAIT * (attempt + 1)
                print(f"  Rate limit, waiting {wait}s... (attempt {attempt+1}/4)")
                time.sleep(wait)
            else:
                print(f"  ERROR on chunk {idx+1}: {e}", file=sys.stderr)
                return chunk
    print(f"  chunk {idx+1} failed after retries, keeping original")
    return chunk


def main():
    args = parse_args()
    md_dir = Path(args.md)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"ERROR: GEMINI_API_KEY not set. Check {ENV_PATH}", file=sys.stderr)
        sys.exit(1)

    # 入力MDの選択
    if args.input_md:
        input_path = Path(args.input_md)
    else:
        input_path = resolve_input_md(md_dir, args.book)

    if not input_path.exists():
        print(f"ERROR: MDファイルが見つかりません -> {input_path}", file=sys.stderr)
        sys.exit(1)

    text = input_path.read_text(encoding="utf-8")
    chunks = split_chunks(text, args.chunk_chars)
    total = len(chunks)

    # 小数の本でも必要な枠を事前に表示
    est_msg = total
    est_books_per_day = 50 // total if total > 0 else 1

    print(f"\n========================================")
    print(f" LLM Fix: {args.book}")
    print(f" Input  : {input_path.name}")
    print(f" Chunks : {total}  ({args.chunk_chars}文字/チャンク)")
    print(f" 今日の視点: {est_msg}チャンク使用 / 50上限")
    print(f" 無料枠でこの本: 一日約{est_books_per_day}冊分処理可")
    print(f"========================================")

    client = genai.Client(api_key=api_key)

    fixed_parts = []
    for i, chunk in enumerate(chunks):
        fixed_parts.append(fix_chunk(client, args.model, chunk, i, total))
        time.sleep(CHUNK_WAIT)

    out_path = md_dir / f"{args.book}_llm_fixed.md"
    out_path.write_text("\n\n".join(fixed_parts), encoding="utf-8")
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
