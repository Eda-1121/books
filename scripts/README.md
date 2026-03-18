# PDF → EPUB 変換マニュアル

## 必要なツール

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)（textモードのみ）
- [Pandoc](https://pandoc.org/)
- Python 3.10+

```powershell
pip install pymupdf google-genai python-dotenv
```

---

## 初回セットアップ

1. `.env.example` をコピーして `scripts\.env` を作成
2. `.env` の `GEMINI_API_KEY` に自分のキーを記入

```powershell
copy E:\Books\pdf2epub\scripts\.env.example E:\Books\pdf2epub\scripts\.env
notepad E:\Books\pdf2epub\scripts\.env
```

Gemini APIキーの取得: https://aistudio.google.com/apikey

---

## フォルダ構成

```
E:\Books\
├── epub\                        # 完成EPUB
├── paddle_output\               # PaddleOCR作業フォルダ（textモードのみ）
│   └── {本名}\
├── pdf\                         # 元PDF（サブフォルダ可）
└── pdf2epub\
    ├── md\                      # 全MDファイル
    └── scripts\
        ├── .env             # APIキー（要作成）
        ├── .env.example     # テンプレート
        ├── run.py           # 全工程一括実行（おすすめ）
        ├── pdf_to_md.py     # PDF→MD（自動判定/Vision/テキスト）
        ├── clean_and_combine.py
        ├── llm_fix.py
        ├── build_epub.py
        └── README.md
```

---

## クイックスタート

```powershell
# 自動判定で全工程実行（おすすめ）
python E:\Books\pdf2epub\scripts\run.py
```

実行後、以下を入力：
```
Book name : 易经
Title      [Enter = 易经]:
Author     [Enter to skip]: 著者名
```

---

## 処理モード

`run.py` および `pdf_to_md.py` は3つのモードをサポートします。

| モード | 内容 | 向いているPDF |
|---|---|---|
| `auto` | PDFを自動判定（デフォルト） | どちらでも |
| `vision` | Gemini Vision OCR | スキャンPDF・画像PDF |
| `text` | 直接テキスト抽出（API不要） | テキスト埋め込みPDF |

### 自動判定の仕組み

先頭5ページの平均文字数で判定します。

```
1ページ平均 ≥ 50文字  →  テキストPDF（textモード）
1ページ平均 < 50文字  →  画像PDF（visionモード）
```

閾値は `--threshold` で変更可能。

---

## run.py 全工程一括実行

### 基本コマンド

```powershell
# 自動判定（おすすめ）
python run.py --book 易经

# 画像PDF（Vision）で完全幸理
 python run.py --book 叔本华论说文集 --mode vision --llm-fix

# テキストPDFをLLM整形なしで高速変換
 python run.py --book 甲与权力 --mode text --skip-llm

# 途中から再開（Visionのみ）
 python run.py --book 叔本华论说文集 --mode vision --resume
```

### ステップ別の処理内容

**Visionモード（画像PDF）:**

| Step | 内容 | 出力 |
|---|---|---|
| 1+3 | Gemini Vision OCR → MD（+ LLM整形） | `md/{book}_vision.md` or `_llm_fixed.md` |
| 4 | MD → EPUB | `epub/{book}.epub` |

**Textモード（テキストPDF）:**

| Step | 内容 | 出力 |
|---|---|---|
| 1 | テキスト抽出 | `md/{book}_vision.md` |
| 2 | PaddleOCR結合（旧来フロー継続用） | `md/{book}_combined.md` |
| 3 | LLM整形 | `md/{book}_llm_fixed.md` |
| 4 | MD → EPUB | `epub/{book}.epub` |

### スキップオプション

```powershell
--skip-ocr      # Step 1 をスキップ（OCR済の場合）
--skip-combine  # Step 2 をスキップ
--skip-llm      # Step 3 をスキップ
--skip-epub     # Step 4 をスキップ
```

---

## pdf_to_md.py 単体実行

```powershell
# 自動判定
python pdf_to_md.py --book 易经

# Vision強制（スキャンPDF）
python pdf_to_md.py --book 叔本华论说文集 --mode vision

# テキスト抽出強制（API不要・高速）
python pdf_to_md.py --book 甲与权力 --mode text

# ページ範囲指定（テスト用）
python pdf_to_md.py --book 叔本华论说文集 --start 1 --end 5

# 途中から再開
python pdf_to_md.py --book 叔本华论说文集 --resume

# Vision + LLM整形を一気に
python pdf_to_md.py --book 叔本华论说文集 --mode vision --llm-fix
```

---

## build_epub.py 単体実行

MDファイルの自動選択優先順位：`_llm_fixed.md` → `_vision.md` → `_combined.md`

```powershell
# 自動選択（おすすめ）
python build_epub.py --book 易经 --title "易经" --author "著者名"

# LLM整形済みを強制使用
python build_epub.py --book 易经 --use-llm

# LLM整形なしで変換
python build_epub.py --book 易经 --no-llm
```

---

## MDファイルの流れ

**Visionモード（画像PDF）:**
```
md\{book}_pages\0001.md ...   ← ページキャッシュ（再開用）
    ↓
md\{book}_vision.md           ← 全ページ結合MD
    ↓ (--llm-fix時)
md\{book}_llm_fixed.md        ← LLM整形済み
    ↓
epub\{book}.epub              ← 完成
```

**Textモード（テキストPDF）:**
```
md\{book}_vision.md           ← テキスト抽出結果
    ↓ (LLM整形時)
md\{book}_llm_fixed.md        ← LLM整形済み
    ↓
epub\{book}.epub              ← 完成
```

**Textモード（PaddleOCR旧来フロー）:**
```
paddle_output\{book}\         ← Step 1: OCR
    ↓
md\{book}_combined.md         ← Step 2: 結合
    ↓
md\{book}_llm_fixed.md        ← Step 3: LLM整形
    ↓
epub\{book}.epub              ← Step 4: 完成
```

---

## 主な引数一覧

### run.py

| 引数 | デフォルト | 内容 |
|---|---|---|
| `--book` | 必須 | 本のタイトル（PDFファイル名） |
| `--mode` | `auto` | `auto` / `vision` / `text` |
| `--llm-fix` | OFF | Vision/auto時にLLM整形も実行 |
| `--model` | `gemini-2.5-flash` | Geminiモデル |
| `--resume` | OFF | ページキャッシュから再開 |
| `--threshold` | `50` | テキストPDF判定の文字数閾値 |
| `--skip-ocr` | OFF | Step 1スキップ |
| `--skip-llm` | OFF | Step 3スキップ |
| `--skip-epub` | OFF | Step 4スキップ |
| `--lang` | `zh-CN` | EPUB言語メタデータ |

### pdf_to_md.py

| 引数 | デフォルト | 内容 |
|---|---|---|
| `--book` | 必須 | 本のタイトル |
| `--mode` | `auto` | `auto` / `vision` / `text` |
| `--llm-fix` | OFF | MD出力後にLLM整形も実行 |
| `--model` | `gemini-2.5-flash` | Geminiモデル |
| `--start` | `1` | 開始ページ |
| `--end` | 最終ページ | 終了ページ |
| `--resume` | OFF | ページキャッシュから再開 |
| `--threshold` | `50` | 自動判定文字数閾値 |
| `--dpi` | `150` | 画像化解像度 |

---

## Free Tier の制限（gemini-2.5-flash）

| 制限 | 値 |
|---|---|
| RPD（1日リクエスト数） | 500 |
| RPM（1分リクエスト数） | 10 |
| TPD（1日1日トークン） | 250万 |

**1日1回処理できる目安: Visionモードで素4旤500ページまで。**

リセット時刻: 太平洋標準時午前0時（JST 17:00）
