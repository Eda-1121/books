# PDF → EPUB 変換マニュアル

## 必要なツール

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) (`paddleocr` コマンド)
- [Pandoc](https://pandoc.org/)
- Python 3.10+

> **環境**: PowerShell で実行することを前提としています。

---

## フォルダ構成

```
E:\Books\
├── epub\                        # 完成EPUB
├── paddle_output\               # OCR作業フォルダ（一時ファイル）
│   ├── 易经\                   # 本ごとのサブフォルダ
│   └── ...
├── pdf\                         # 元PDF（サブフォルダ可）
└── pdf2epub\                     # 作業フォルダ
    ├── md\                      # 結合・EPUB用MD
    └── scripts\                 # スクリプト
        ├── run.py           # ★ 一括実行（推奨）
        ├── clean_and_combine.py
        ├── fix_and_build.py
        └── README.md
```

---

## 基本の使い方（推奨）

```powershell
python E:\Books\pdf2epub\scripts\run.py
```

実行後、以下のように入力を求められます：

```
========================================
 PDF → EPUB コンバーター
========================================
Book name : 易经
Title      [Enter = 摑经]: 
 Author     [Enter to skip]: 著者名
```

- **Book name**: `E:\Books\pdf\` 以下のPDFファイル名（拡張子なし）
- **Title**: Enterで本の名前をそのまま使用
- **Author**: Enterでスキップ可能

完成ファイル: `E:\Books\epub\{本の名前}.epub`

---

## 引数で指定する場合

```powershell
python E:\Books\pdf2epub\scripts\run.py --book 易经 --title "易经" --author "著者名"
```

**run.py のオプション：**

| オプション | デフォルト | 説明 |
|---|---|---|
| `--book` | （対話入力） | 本の名前 |
| `--title` | bookと同じ | EPUBのタイトル |
| `--author` | 空 | EPUBの著者名 |
| `--lang` | `zh-CN` | 言語コード |
| `--skip-ocr` | なし | OCRをスキップ（MDが既存の場合） |
| `--pdf` | `E:\Books\pdf` | PDF元フォルダ |
| `--paddle` | `E:\Books\paddle_output` | OCR出力フォルダ |
| `--md` | `E:\Books\pdf2epub\md` | MD保存先 |
| `--epub` | `E:\Books\epub` | EPUB保存先 |

---

## 内部動作（各Stepの詳細）

### Step 1 — OCR（PDF → Markdown）

```powershell
paddleocr pp_structurev3 -i "E:\Books\pdf\{本の名前}.pdf" --use_doc_orientation_classify False --use_doc_unwarping False --use_formula_recognition False --save_path "E:\Books\paddle_output\{本の名前}"
```

### Step 2 — MD結合・クリーンアップ

```powershell
python E:\Books\pdf2epub\scripts\clean_and_combine.py --book {本の名前}
```

処理内容：`paddle_output\{本の名前}\` 内のMDを結合 → `pdf2epub\md\{本の名前}_combined.md` を生成、不要ファイルを自動削除

### Step 3 — MD整形・EPUBビルド

```powershell
python E:\Books\pdf2epub\scripts\fix_and_build.py --book {本の名前} --title "表示タイトル" --author "著者名"
```

処理内容：OCRノイズ除去・見出し整理 → `pdf2epub\md\{本の名前}_fixed.md` を生成しEPUB化

---

## MDを手動で修正したい場合

Step 2 完了後、`pdf2epub\md\{本の名前}_combined.md` を編集してから、`--skip-ocr` を付けて実行：

```powershell
python E:\Books\pdf2epub\scripts\run.py --skip-ocr
```

---

## 出力ファイルの流れ

```
paddle_output\{本の名前}\{本の名前}_0.md ~ _N.md   # Step 1: PaddleOCR生成
    ↓ clean_and_combine.py
pdf2epub\md\{本の名前}_combined.md                  # Step 2: 結合済み
    ↓ fix_and_build.py
pdf2epub\md\{本の名前}_fixed.md                    # Step 3: 整形済み
    ↓ pandoc
epub\{本の名前}.epub                               # 完成
```
