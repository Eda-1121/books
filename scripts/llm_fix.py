#!/usr/bin/env python3
"""
llm_fix.py
_combined.md を Gemini API で整形し _llm_fixed.md を生成する。

Dependencies:
    pip install google-genai python-dotenv

Usage:
    python E:\\Books\\pdf2epub\\scripts\\llm_fix.py --book 易经
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

SYSTEM_PROMPT = """あなたは書籍の編集者です。
OCRで取得したMarkdownテキストを整形するタスクを行います。
以下のルールに従ってください：

1. 内容は一切変えず、レイアウトと構造のみ修正する
2. 第N章、第N節などの章節見出しは # または ## の見出しに変換する
3. OCRノイズ（意味のない記号、孤立した$や+など）を削除する
4. 改行が不自然な箇所を修正して文章を自然な流れにする
5. 表や箇条書きは正しいMarkdown構文に変換する
6. 画像参照（![...](...)）はそのまま保持する
7. 出力はMarkdown形式のみ。説明文や前置きは一切不要
"""

CHUNK_CHARS = 12000
RETRY_WAIT  = 10


def parse_args():
    p = argparse.ArgumentParser(description="LLMでMDを整形")
    p.add_argument("--book",  required=True)
    p.add_argument("--md",    default=r"E:\Books\pdf2epub\md")
    p.add_argument("--model", default="gemini-2.0-flash")
    return p.parse_args()


def split_chunks(text: str, max_chars: int) -> list[str]:
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
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            print(f"  chunk {idx+1}/{total} done")
            return response.text
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "RESOURCE_EXHAUSTED" in err:
                print(f"  Rate limit, waiting {RETRY_WAIT}s...")
                time.sleep(RETRY_WAIT)
            else:
                print(f"  ERROR on chunk {idx+1}: {e}", file=sys.stderr)
                return chunk
    return chunk


def main():
    args = parse_args()
    md_dir = Path(args.md)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"ERROR: GEMINI_API_KEY not set. Check {ENV_PATH}", file=sys.stderr)
        sys.exit(1)

    combined_path = md_dir / f"{args.book}_combined.md"
    if not combined_path.exists():
        print(f"ERROR: not found -> {combined_path}", file=sys.stderr)
        sys.exit(1)

    text = combined_path.read_text(encoding="utf-8")
    chunks = split_chunks(text, CHUNK_CHARS)
    total = len(chunks)
    print(f"\n========================================")
    print(f" LLM Fix: {args.book}  ({total} chunks)")
    print(f"========================================")

    client = genai.Client(api_key=api_key)

    fixed_parts = []
    for i, chunk in enumerate(chunks):
        fixed_parts.append(fix_chunk(client, args.model, chunk, i, total))
        time.sleep(1)

    out_path = md_dir / f"{args.book}_llm_fixed.md"
    out_path.write_text("\n\n".join(fixed_parts), encoding="utf-8")
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
