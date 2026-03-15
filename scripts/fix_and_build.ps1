param(
    [Parameter(Mandatory=$true)]
    [string]$BookName,

    [string]$PaddleOutput = "E:\Books\paddle_output",
    [string]$EpubOutput   = "E:\Books\epub",
    [string]$BookTitle    = "",
    [string]$BookAuthor   = "",
    [string]$BookLang     = "zh-CN",
    [int]$MinImageKB      = 5
)

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
New-Item -ItemType Directory -Force -Path $EpubOutput | Out-Null
if (-not $BookTitle) { $BookTitle = $BookName }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Fix & Build EPUB: $BookTitle"           -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Script  : $PSCommandPath"
Write-Host "  Input   : $PaddleOutput\${BookName}_combined.md"
Write-Host "  Output  : $EpubOutput\${BookName}.epub"

# ------------------------------------------------
# Step 1: read combined.md
# ------------------------------------------------
Write-Host "`n[1/7] Reading combined markdown..." -ForegroundColor Yellow
$combinedPath = "$PaddleOutput\${BookName}_combined.md"
if (-not (Test-Path $combinedPath)) {
    Write-Host "ERROR: not found -> $combinedPath" -ForegroundColor Red; exit 1
}
$text = [System.IO.File]::ReadAllText($combinedPath, [System.Text.Encoding]::UTF8)
Write-Host "  OK: $combinedPath"

# ------------------------------------------------
# Step 2: filter missing / tiny images
# ------------------------------------------------
Write-Host "`n[2/7] Filtering images..." -ForegroundColor Yellow
$kept = 0; $removed = 0

$text = [regex]::Replace($text, '<div[^>]*><img\s+src="([^"]*)"[^>]*></div>', {
    param($m)
    $p = Join-Path $PaddleOutput $m.Groups[1].Value
    if ((Test-Path $p) -and ((Get-Item $p).Length/1024 -ge $MinImageKB)) {
        $script:kept++; return $m.Value
    }; $script:removed++; return ''
})
$text = [regex]::Replace($text, '!\[([^\]]*)\]\(([^)]*)\)', {
    param($m)
    $p = Join-Path $PaddleOutput $m.Groups[2].Value
    if ((Test-Path $p) -and ((Get-Item $p).Length/1024 -ge $MinImageKB)) {
        $script:kept++; return $m.Value
    }; $script:removed++; return ''
})
Write-Host "  Kept: $kept  Removed: $removed (missing or < ${MinImageKB}KB)"

# ------------------------------------------------
# Step 3: remove OCR noise  (+++ / $$ etc.)
# ------------------------------------------------
Write-Host "`n[3/7] Removing OCR noise..." -ForegroundColor Yellow
# remove +++ at start of heading lines
$text = [regex]::Replace($text, '(?m)^(#{1,6}\s*)\+{2,}\s*', '$1')
# remove lines that are only $ or $$
$text = [regex]::Replace($text, '(?m)^\$+\s*$', '')
$text = [regex]::Replace($text, '(?m)^#{1,6}\s*\$+\s*$', '')
Write-Host "  Done"

# ------------------------------------------------
# Step 4: fix chapter headings
# ------------------------------------------------
Write-Host "`n[4/7] Fixing chapter headings..." -ForegroundColor Yellow

# "# 3 谢只" -> "# 序言"
$text = [regex]::Replace($text, '(?m)^#{1,6}\s*3\s*\u8c22\u53ea', '# \u5e8f\u8a00')
# "## 一 切为了您的阅读体验" -> "## 一切为了您的阅读体验"
$text = [regex]::Replace($text, '(?m)^#{1,6}\s*\u4e00\s+\u5207\u4e3a\u4e86\u60a8\u7684\u9605\u8bfb\u4f53\u9a8c', '## \u4e00\u5207\u4e3a\u4e86\u60a8\u7684\u9605\u8bfb\u4f53\u9a8c')
# "尾声瞬间的影响 Influence:..." -> clean title
$text = $text -replace '\u5c3e\u58f0\u77ac\u95f4\u7684\u5f71\u54cd\s*Influence[^\n]*', '\u5c3e\u58f0 \u77ac\u95f4\u7684\u5f71\u54cd'

# force 第N章 headings to h1
$text = [regex]::Replace($text, '(?m)^#{2,6}\s*(\u7b2c\d+\u7ae0)', '# $1')

# force known top-level headings to h1
foreach ($h in @('\u5e8f\u8a00','\u5f15\u8a00','\u5c3e\u58f0','\u8bfb\u8005\u62a5\u544a','\u5f71\u54cd\u529b\u6c34\u5e73\u6d4b\u8bd5','\u4f5c\u8005\u70b9\u8bc4')) {
    $text = [regex]::Replace($text, "(?m)^#{2,6}\s*($h)", '# $1')
}
Write-Host "  Done"

# ------------------------------------------------
# Step 5: remove duplicate TOC block
# ------------------------------------------------
Write-Host "`n[5/7] Removing duplicate TOC block..." -ForegroundColor Yellow
$text = [regex]::Replace(
    $text,
    '\u7f16\u8f91\u624b\u8bb0[\s\S]{0,20}\u5173\u4e8e\u300a\u5f71\u54cd\u529b\u300b[\s\S]*?\u7b2c1\u7ae0\u5f71\u54cd\u529b\u7684\u6b66\u5668[^\n]*\n',
    '',
    [System.Text.RegularExpressions.RegexOptions]::Singleline
)
Write-Host "  Done"

# ------------------------------------------------
# Step 6: format 专家解读 blocks as blockquotes
# ------------------------------------------------
Write-Host "`n[6/7] Formatting expert commentary blocks..." -ForegroundColor Yellow
$text = [regex]::Replace(
    $text,
    '(?m)^\u4e13\u5bb6[^\n]*\n\u89e3\u8bfb[^\n]*\n([\s\S]*?)(?=\n\n|\n#)',
    {
        param($m)
        $inner = $m.Groups[1].Value.Trim() -replace '(?m)^', '> '
        return "`n> **\u300a\u4e13\u5bb6\u89e3\u8bfb\u300b**`n$inner`n"
    }
)
Write-Host "  Done"

# ------------------------------------------------
# common cleanup
# ------------------------------------------------
# compress 4+ blank lines to 2
$text = [regex]::Replace($text, '(\r?\n){4,}', "`n`n`n")
# strip trailing spaces
$text = [regex]::Replace($text, '(?m) +$', '')

# ------------------------------------------------
# Step 7: save fixed.md -> build EPUB
# ------------------------------------------------
Write-Host "`n[7/7] Writing fixed markdown & building EPUB..." -ForegroundColor Yellow

$finalPath = "$PaddleOutput\${BookName}_fixed.md"
[System.IO.File]::WriteAllText($finalPath, $text, $utf8NoBom)
Write-Host "  Saved: $finalPath"

# CSS
$cssPath = "$PaddleOutput\epub_style.css"
$css = @'
@charset "UTF-8";
body {
    font-family: "Noto Serif CJK SC","Source Han Serif SC","Songti SC","SimSun","STSong",serif;
    font-size: 1em; line-height: 1.8; text-align: justify;
    margin: 1em; color: #1a1a1a;
}
h1 {
    font-size: 1.6em; font-weight: bold; text-align: center;
    margin-top: 2em; margin-bottom: 1.5em;
    page-break-before: always;
    border-bottom: 1px solid #ccc; padding-bottom: 0.5em; color: #333;
}
h1:first-of-type { page-break-before: avoid; }
h2 { font-size: 1.3em; font-weight: bold; margin-top: 1.5em; margin-bottom: 0.8em; color: #444; }
h3 { font-size: 1.1em; font-weight: bold; margin-top: 1.2em; margin-bottom: 0.6em; color: #555; }
p  { text-indent: 2em; margin-top: 0.3em; margin-bottom: 0.3em; }
blockquote {
    margin: 1em 1.5em; padding: 0.6em 1em;
    border-left: 3px solid #aaa;
    background: #f9f9f9; color: #555; font-size: 0.95em;
}
img { max-width: 100%; height: auto; display: block; margin: 1em auto; }
nav#toc ol { list-style-type: none; padding-left: 0; }
nav#toc li { margin: 0.5em 0; }
'@
[System.IO.File]::WriteAllText($cssPath, $css, $utf8NoBom)

# output epub name matches existing convention: BookName.epub (not _fixed)
$epubPath = "$EpubOutput\${BookName}.epub"
$pandocArgs = @(
    $finalPath, "-o", $epubPath,
    "--metadata", "title=$BookTitle",
    "--metadata", "lang=$BookLang",
    "-f", "markdown", "-t", "epub3",
    "--css=$cssPath",
    "--resource-path=$PaddleOutput",
    "--epub-chapter-level=1",
    "--toc", "--toc-depth=2"
)
if ($BookAuthor) { $pandocArgs += "--metadata"; $pandocArgs += "author=$BookAuthor" }

& pandoc $pandocArgs 2>&1

if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host " EPUB created: $epubPath"                 -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host "`n  Completed with warnings: $epubPath" -ForegroundColor Yellow
}
