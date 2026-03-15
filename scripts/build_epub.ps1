param(
    [Parameter(Mandatory=$true)]
    [string]$BookName,
    
    [string]$PaddleOutput = "E:\Books\paddle_output",
    [string]$EpubOutput = "E:\Books\epub",
    
    [int]$MinImageKB = 5,
    
    [string]$BookTitle = "",
    [string]$BookAuthor = "",
    [string]$BookLang = "zh-CN"
)

# ============================================================
# PDF -> PaddleOCR -> EPUB 変換・整形スクリプト
# ============================================================

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
New-Item -ItemType Directory -Force -Path $EpubOutput | Out-Null

if (-not $BookTitle) { $BookTitle = $BookName }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " EPUB Builder: $BookTitle" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# --- Step 1: Collect and sort MD files ---
Write-Host "`n[1/6] Collecting Markdown files..." -ForegroundColor Yellow
$mdFiles = Get-ChildItem "$PaddleOutput\${BookName}_*.md" -Exclude "*combined*" | 
    Sort-Object { [int]($_.BaseName -replace "${BookName}_",'') }

if ($mdFiles.Count -eq 0) {
    Write-Host "ERROR: No markdown files found for '$BookName' in $PaddleOutput" -ForegroundColor Red
    exit 1
}
Write-Host "  Found $($mdFiles.Count) pages"

# --- Step 2: Combine all pages ---
Write-Host "`n[2/6] Combining pages..." -ForegroundColor Yellow
$allContent = @()
foreach ($f in $mdFiles) {
    $text = [System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::UTF8)
    $allContent += $text
}
$combined = $allContent -join "`n`n"

# --- Step 3: Remove small/decorative images ---
Write-Host "`n[3/6] Filtering images..." -ForegroundColor Yellow
$imgDir = Join-Path $PaddleOutput "imgs"
$removedImages = 0
$keptImages = 0

# Remove image references where file doesn't exist or is too small
$combined = [regex]::Replace($combined, '<div[^>]*><img\s+src="([^"]*)"[^>]*></div>', {
    param($m)
    $imgRelPath = $m.Groups[1].Value
    $imgFullPath = Join-Path $PaddleOutput $imgRelPath
    if (Test-Path $imgFullPath) {
        $size = (Get-Item $imgFullPath).Length / 1024
        if ($size -lt $MinImageKB) {
            $script:removedImages++
            return ''
        }
        $script:keptImages++
        return $m.Value
    }
    $script:removedImages++
    return ''
})

$combined = [regex]::Replace($combined, '!\[([^\]]*)\]\(([^)]*)\)', {
    param($m)
    $imgRelPath = $m.Groups[2].Value
    $imgFullPath = Join-Path $PaddleOutput $imgRelPath
    if (Test-Path $imgFullPath) {
        $size = (Get-Item $imgFullPath).Length / 1024
        if ($size -lt $MinImageKB) {
            $script:removedImages++
            return ''
        }
        $script:keptImages++
        return $m.Value
    }
    $script:removedImages++
    return ''
})

Write-Host "  Kept: $keptImages images, Removed: $removedImages images (< ${MinImageKB}KB or missing)"

# --- Step 4: Fix headings and structure ---
Write-Host "`n[4/6] Fixing headings and structure..." -ForegroundColor Yellow

# Fix common OCR heading errors
# Remove noise characters from chapter headings
$combined = $combined -replace '#{1,3}\s*\$+\s*$', '' 
$combined = $combined -replace '#{1,3}\s*\+\+\+', '## '

# Fix known chapter heading patterns for 影响力
$chapterFixes = @{
    '3 谢只' = '序言'
    '第3章承诺和一致中的' = '第3章 承诺和一致'
    '们 第4章社会认同就' = '第4章 社会认同'
    '尾声瞬间的影响 Influence:The Psychology of Persuasion' = '尾声 瞬间的影响'
    '尾声瞬间的影响 PsychalogyofPersuasion' = '读者报告'
    '一 切为了您的阅读体验' = '一切为了您的阅读体验'
}

foreach ($old in $chapterFixes.Keys) {
    $combined = $combined -replace [regex]::Escape($old), $chapterFixes[$old]
}

# Standardize chapter headings to h1 (# )
# Match patterns like "第N章 ..." and ensure they are h1
$combined = [regex]::Replace($combined, '(?m)^#{2,6}\s*(第\d+章)', '# $1')

# Ensure these are h1
foreach ($h1 in @('序言', '引言', '尾声', '读者报告', '影响力水平测试')) {
    $combined = [regex]::Replace($combined, "(?m)^#{2,6}\s*($h1)", '# $1')
}

# Clean up empty lines (reduce 3+ consecutive empty lines to 2)
$combined = [regex]::Replace($combined, '(\r?\n){4,}', "`n`n`n")

# Remove lines that are just "$" or "$$" (OCR artifacts)
$combined = [regex]::Replace($combined, '(?m)^\$+\s*$', '')

Write-Host "  Headings and structure cleaned"

# --- Step 5: Write combined markdown ---
Write-Host "`n[5/6] Writing combined markdown..." -ForegroundColor Yellow
$combinedPath = Join-Path $PaddleOutput "${BookName}_final.md"
[System.IO.File]::WriteAllText($combinedPath, $combined, $utf8NoBom)
Write-Host "  Saved: $combinedPath"

# --- Step 6: Create CSS and convert to EPUB ---
Write-Host "`n[6/6] Converting to EPUB..." -ForegroundColor Yellow

# Create stylesheet
$cssPath = Join-Path $PaddleOutput "epub_style.css"
$css = @'
/* EPUB Stylesheet for Chinese Books */
@charset "UTF-8";

body {
    font-family: "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", "SimSun", "STSong", serif;
    font-size: 1em;
    line-height: 1.8;
    text-align: justify;
    margin: 1em;
    color: #1a1a1a;
}

h1 {
    font-size: 1.6em;
    font-weight: bold;
    text-align: center;
    margin-top: 2em;
    margin-bottom: 1.5em;
    page-break-before: always;
    border-bottom: 1px solid #ccc;
    padding-bottom: 0.5em;
    color: #333;
}

h1:first-of-type {
    page-break-before: avoid;
}

h2 {
    font-size: 1.3em;
    font-weight: bold;
    margin-top: 1.5em;
    margin-bottom: 0.8em;
    color: #444;
}

h3 {
    font-size: 1.1em;
    font-weight: bold;
    margin-top: 1.2em;
    margin-bottom: 0.6em;
    color: #555;
}

p {
    text-indent: 2em;
    margin-top: 0.3em;
    margin-bottom: 0.3em;
}

blockquote {
    margin: 1em 2em;
    padding: 0.5em 1em;
    border-left: 3px solid #ccc;
    color: #555;
    font-style: italic;
}

img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
}

div[style*="text-align: center"] img {
    margin: 1.5em auto;
}

/* Table of Contents */
nav#toc ol {
    list-style-type: none;
    padding-left: 0;
}

nav#toc li {
    margin: 0.5em 0;
}
'@
[System.IO.File]::WriteAllText($cssPath, $css, $utf8NoBom)

# Build EPUB with pandoc
$epubPath = Join-Path $EpubOutput "$BookName.epub"

$pandocArgs = @(
    $combinedPath,
    "-o", $epubPath,
    "--metadata", "title=$BookTitle",
    "--metadata", "lang=$BookLang",
    "-f", "markdown",
    "-t", "epub3",
    "--css=$cssPath",
    "--resource-path=$PaddleOutput",
    "--epub-chapter-level=1",
    "--toc",
    "--toc-depth=2"
)

if ($BookAuthor) {
    $pandocArgs += "--metadata"
    $pandocArgs += "author=$BookAuthor"
}

& pandoc $pandocArgs 2>&1

if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host " EPUB created: $epubPath" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host "`n  EPUB conversion completed with warnings" -ForegroundColor Yellow
    Write-Host "  Output: $epubPath" -ForegroundColor Yellow
}

# Cleanup: remove intermediate debug images from paddle output
Write-Host "`nOptional: To clean up PaddleOCR debug files, run:"
Write-Host "  Remove-Item '$PaddleOutput\*.json'"
Write-Host "  Remove-Item '$PaddleOutput\*.png'"
Write-Host "  Remove-Item '$PaddleOutput\*.docx'"
Write-Host "  Remove-Item '$PaddleOutput\*.tex'"
