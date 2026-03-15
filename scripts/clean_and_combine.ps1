param(
    [string]$BookName,
    [string]$PaddleOutput = "E:\Books\paddle_output",
    [string]$EpubOutput = "E:\Books\epub"
)

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
New-Item -ItemType Directory -Force -Path $EpubOutput | Out-Null

# MDファイルをページ順に結合
$files = Get-ChildItem "$PaddleOutput\${BookName}_*.md" -Exclude "*combined*" |
    Sort-Object { [int]($_.BaseName -replace "${BookName}_",'') }

$lines = @()
foreach ($f in $files) {
    $text = [System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::UTF8)

    # <div><img src="..."></div> 形式: 画像が存在しなければ削除
    $text = [regex]::Replace($text, '<div[^>]*><img\s+src="([^"]*)"[^>]*></div>', {
        param($m)
        $imgPath = Join-Path $PaddleOutput $m.Groups[1].Value
        if (Test-Path $imgPath) { $m.Value } else { '' }
    })

    # ![alt](path) 形式: 画像が存在しなければ削除
    $text = [regex]::Replace($text, '!\[[^\]]*\]\(([^)]*)\)', {
        param($m)
        $imgPath = Join-Path $PaddleOutput $m.Groups[1].Value
        if (Test-Path $imgPath) { $m.Value } else { '' }
    })

    $lines += $text
}

$combined = $lines -join "`n`n"
$combinedPath = "$PaddleOutput\${BookName}_combined.md"
[System.IO.File]::WriteAllText($combinedPath, $combined, $utf8NoBom)

Write-Host "Combined MD: $combinedPath"

# pandocでEPUB変換
$epubPath = "$EpubOutput\${BookName}.epub"
pandoc $combinedPath -o $epubPath --metadata title="$BookName" -f markdown -t epub3 --resource-path="$PaddleOutput"

Write-Host "EPUB created: $epubPath"
