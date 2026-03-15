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
# Step 4: fix chapter headings (use actual Unicode chars, not escape literals)
# ------------------------------------------------
Write-Host "`n[4/7] Fixing chapter headings..." -ForegroundColor Yellow

# "# 3 谢只" -> "# 序言"
$text = [regex]::Replace($text, '(?m)^#{1,6}\s*3\s*谢只', '# 序言')
# "## 一 切为了您的阅读体验" -> "## 一切为了您的阅读体验"
$text = [regex]::Replace($text, '(?m)^#{1,6}\s*一\s+切为了您的阅读体验', '## 一切为了您的阅读体验')
# "尾声瞬间的影响 Influence:..." -> clean title
$text = $text -replace '尾声瞬间的影响\s*Influence[^\n]*', '尾声 瞬间的影响'

# force 第N章 headings to h1
$text = [regex]::Replace($text, '(?m)^#{2,6}\s*(第\d+章)', '# $1')

# force known top-level headings to h1
foreach ($h in @('序言','引言','尾声','读者报告','影响力水平测试','作者点评')) {
    $text = [regex]::Replace($text, "(?m)^#{2,6}\s*($h)", '# $1')
}
Write-Host "  Done"

# ------------------------------------------------
# Step 4b: convert any remaining \uXXXX literals to real characters
# ------------------------------------------------
Write-Host "`n[4b] Converting leftover Unicode escape literals..." -ForegroundColor Yellow
$text = [regex]::Replace($text, '\\u([0-9a-fA-F]{4})', {
    param($m)
    [char][Convert]::ToInt32($m.Groups[1].Value, 16)
})
Write-Host "  Done"

# ------------------------------------------------
# Step 5: remove duplicate TOC block
# ------------------------------------------------
Write-Host "`n[5/7] Removing duplicate TOC block..." -ForegroundColor Yellow
$text = [regex]::Replace(
    $text,
    '编辑手记[\s\S]{0,20}关于《影响力》[\s\S]*?第1章影响力的武器[^\n]*\n',
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
    '(?m)^专家[^\n]*\n解读[^\n]*\n([\s\S]*?)(?=\n\n|\n#)',
    {
        param($m)
        $inner = $m.Groups[1].Value.Trim() -replace '(?m)^', '> '
        return "`n> **《专家解读》**`n$inner`n"
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
