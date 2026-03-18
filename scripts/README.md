# PDF → EPUB 変換マニュアル

## 必要なツール

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [Pandoc](https://pandoc.org/)
- Python 3.10+
- `pip install google-generativeai python-dotenv`

---

## 初回セットアップ

1. `.env.example` をコピーして `.env` を作成
2. `.env` の `GEMINI_API_KEY` に自分のキーを記入

```powershell
cd E:\Books
copy .env.example .env
notepad .env
```

---

## フォルダ構成

```
E:\Books\
├── .env                         # APIキー（要作成）
├── .env.example                 # テンプレート
├── epub\                        # 完成EPUB
├── paddle_output\               # OCR作業フォルダ
│   └── {本名}\
├── pdf\                         # 元PDF
└── pdf2epub\
    ├── md\                      # MDファイル
    └── scripts\
        ├── run.py           # ★ 一括実行
        ├── clean_and_combine.py  # Step 2
        ├── llm_fix.py            # Step 3
        ├── build_epub.py         # Step 4
        └── README.md
```

---

## 基本の使い方

```powershell
python E:\Books\pdf2epub\scripts\run.py
```

実行後、以下を入力：

```
Book name : 易经
Title      [Enter = 易经]:
Author     [Enter to skip]: 著者名
```

---

## 処理ステップ

| Step | スクリプト | 内容 | 出力 |
|---|---|---|---|
| 1 | OCR | PDF→MD (PaddleOCR) | `paddle_output/{book}/` |
| 2 | Combine | ページ結合・クリーンアップ | `md/{book}_combined.md` |
| 3 | LLM Fix | Geminiで整形 | `md/{book}_llm_fixed.md` |
| 4 | EPUB | pandocでEPUB化 | `epub/{book}.epub` |

---

## 个別実行

```powershell
# Step 2のみ
python E:\Books\pdf2epub\scripts\clean_and_combine.py --book 易经

# Step 3のみ
python E:\Books\pdf2epub\scripts\llm_fix.py --book 易经

# Step 4のみ
python E:\Books\pdf2epub\scripts\build_epub.py --book 易经 --title "易经" --author "著者名"
```

---

## スキップオプション

```powershell
# OCR済みの場合（Step 1をスキップ）
python run.py --skip-ocr

# LLM整形なしでEPUB化
python run.py --skip-llm

# OCRと結合のみ（EPUB化なし）
python run.py --skip-llm --skip-epub
```

---

## MDを手動修正する場合

Step 3完了後、`md\{book}_llm_fixed.md` を編集してから：

```powershell
python E:\Books\pdf2epub\scripts\build_epub.py --book 易经 --title "易经"
```

---

## 出力ファイルの流れ

```
paddle_output\{book}\{book}_N.md     # Step 1: OCR
    ↓ clean_and_combine.py
md\{book}_combined.md                # Step 2: 結合
    ↓ llm_fix.py
md\{book}_llm_fixed.md               # Step 3: LLM整形
    ↓ build_epub.py
epub\{book}.epub                     # Step 4: 完成
```
