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
├── paddle_output\
│   ├── 易经\          # 本ごとのサブフォルダ
│   ├── 影响力\
│   └── ...
└── epub\
    ├── 易经.epub
    ├── 影响力.epub
    └── ...
```

---

## 手順

### Step 1 — OCR（PDF → Markdown）

```powershell
paddleocr pp_structurev3 -i "E:\Books\{本の名前}.pdf" --use_doc_orientation_classify False --use_doc_unwarping False --save_path "E:\Books\paddle_output\{本の名前}"
```

実行後、`paddle_output\{本の名前}\` に `{本の名前}_0.md`, `{本の名前}_1.md` ... が生成されます。

---

### Step 2 — MD結合・クリーンアップ

```powershell
python scripts/clean_and_combine.py --book {本の名前}
```

**処理内容：**
- `paddle_output\{本の名前}\` 内のMDを番号順に結合 → `{本の名前}_combined.md` を生成
- 存在しない画像参照を削除
- 不要ファイルを自動削除（`.docx` / `.tex` / `*_res.json` / デバッグPNG）

**オプション：**

| オプション | デフォルト | 説明 |
|---|---|---|
| `--book` | （必須） | 本の名前（ファイル名と一致） |
| `--paddle` | `E:\Books\paddle_output` | PaddleOCRベース出力フォルダ |
| `--epub` | `E:\Books\epub` | EPUB保存先フォルダ |

---

### Step 3 — MDを整形してEPUBをビルド

```powershell
python scripts/fix_and_build.py --book {本の名前} --title "表示タイトル" --author "著者名"
```

**処理内容：**
- OCRノイズ除去（記号のみの行など）
- `第N章` パターンをh1見出しに統一
- 小さい・存在しない画像参照を削除
- CSSスタイル付きEPUB3を生成 → `epub\{本の名前}.epub`

**オプション：**

| オプション | デフォルト | 説明 |
|---|---|---|
| `--book` | （必須） | 本の名前 |
| `--title` | bookと同じ | EPUBのタイトルメタデータ |
| `--author` | 空 | EPUBの著者メタデータ |
| `--lang` | `zh-CN` | 言語コード |
| `--paddle` | `E:\Books\paddle_output` | 作業ベースフォルダ |
| `--epub` | `E:\Books\epub` | EPUB保存先フォルダ |
| `--min-image-kb` | `5` | この値未満の画像は除外（KB） |

---

## 実行例（易经）

```powershell
# Step 1: OCR
paddleocr pp_structurev3 -i "E:\Books\易经.pdf" --use_doc_orientation_classify False --use_doc_unwarping False --save_path "E:\Books\paddle_output\易经"

# Step 2: 結合・クリーンアップ
python scripts/clean_and_combine.py --book 易经

# Step 3: 整形・EPUB化
python scripts/fix_and_build.py --book 易经 --title "易经" --author "著者名"
```

完成ファイル: `E:\Books\epub\易经.epub`

---

## MDを手動で修正したい場合

Step 2 完了後、`paddle_output\{本の名前}\{本の名前}_combined.md` を直接編集してから Step 3 を実行してください。

---

## 出力ファイルの流れ

```
{本の名前}_0.md ~ _N.md   # PaddleOCR生成（Step 1）
    ↓ clean_and_combine.py
{本の名前}_combined.md     # 結合済み（Step 2）
    ↓ fix_and_build.py
{本の名前}_fixed.md        # 整形済み（Step 3中間）
    ↓ pandoc
{本の名前}.epub            # 完成（Step 3）
```
