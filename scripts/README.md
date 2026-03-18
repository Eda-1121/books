# PDF → EPUB 変換マニュアル

## 必要なツール

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [Pandoc](https://pandoc.org/)
- Python 3.10+

```powershell
pip install google-generativeai python-dotenv pymupdf
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
├── paddle_output\               # OCR作業フォルダ　※方法1のみ使用
│   └── {本名}\
├── pdf\                         # 元PDF（サブフォルダ可）
└── pdf2epub\
    ├── md\                      # 全MDファイル
    └── scripts\
        ├── .env             # APIキー（要作成）
        ├── .env.example     # テンプレート
        ├── run.py           # 方法1: 一括実行
        ├── pdf_to_md.py     # 方法2: PDF→MD（Vision直接）
        ├── clean_and_combine.py
        ├── llm_fix.py
        ├── build_epub.py
        └── README.md
```

---

## 方法1: OCR + LLM整形（推奨）

PaddleOCRでテキスト抽出 → Geminiで構造整形。
**APIコストが少ない。**

```powershell
python E:\Books\pdf2epub\scripts\run.py
```

実行後、以下を入力：
```
Book name : 易经
Title      [Enter = 易经]:
Author     [Enter to skip]: 著者名
```

### 処理ステップ

| Step | スクリプト | 内容 | 出力 |
|---|---|---|---|
| 1 | `run.py` 内 | PDF→OCR (PaddleOCR) | `paddle_output/{book}/` |
| 2 | `clean_and_combine.py` | ページ結合・クリーンアップ | `md/{book}_combined.md` |
| 3 | `llm_fix.py` | GeminiでMD整形 | `md/{book}_llm_fixed.md` |
| 4 | `build_epub.py` | MD→EPUB | `epub/{book}.epub` |

### スキップオプション

```powershell
# OCR済みの場合
python run.py --skip-ocr

# EPUB化は後で手動でやる
python run.py --skip-epub

# LLM整形なし
python run.py --skip-llm
```

---

## 方法2: PDF → MD（Gemini Vision直接）

PDFページを画像化してGeminiにVision解析させる。
**レイアウト誤認が少ない。APIコストが高い。**

```powershell
# 全ページ処理
python E:\Books\pdf2epub\scripts\pdf_to_md.py --book 易经

# ページ範囲指定（テスト用）
python E:\Books\pdf2epub\scripts\pdf_to_md.py --book 易经 --start 1 --end 10

# 途中から再開
python E:\Books\pdf2epub\scripts\pdf_to_md.py --book 易经 --resume
```

### 出力ファイル

| ファイル | 内容 |
|---|---|
| `md/{book}_vision.md` | 全ページ結合済みMD |
| `md/{book}_pages/0001.md` ... | ページ別キャッシュ（再開用） |

### Vision MD → EPUB

```powershell
# _vision.md を _llm_fixed.md にリネームしてから実行
Rename-Item "E:\Books\pdf2epub\md\{本名}_vision.md" "{本名}_llm_fixed.md"
python E:\Books\pdf2epub\scripts\build_epub.py --book 易经 --title "易经" --author "著者名"
```

---

## MDを手動修正してEPUB化

```powershell
# MDを確認・編集
notepad E:\Books\pdf2epub\md\{本名}_llm_fixed.md

# EPUB化
python E:\Books\pdf2epub\scripts\build_epub.py --book {本名} --title "タイトル" --author "著者名"
```

---

## 出力ファイルの流れ

**方法1（OCR + LLM）:**
```
paddle_output\{book}\{book}_N.md   # Step 1: OCR
    ↓
md\{book}_combined.md              # Step 2: 結合
    ↓
md\{book}_llm_fixed.md             # Step 3: LLM整形
    ↓
epub\{book}.epub                   # Step 4: 完成
```

**方法2（Vision直接）:**
```
md\{book}_pages\0001.md ...        # ページ別キャッシュ
    ↓
md\{book}_vision.md                # 結合MD
    ↓ (リネーム or 手動編集)
epub\{book}.epub                   # 完成
```
