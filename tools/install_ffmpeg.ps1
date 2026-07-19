[CmdletBinding()]
param(
    [string] $DownloadUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    [string] $Destination
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Destination) {
    $Destination = Join-Path $repoRoot "vendor\ffmpeg"
}

$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$tempRoot = Join-Path $tempBase ("hotelcut-ffmpeg-" + [guid]::NewGuid().ToString("N"))
$resolvedTemp = [System.IO.Path]::GetFullPath($tempRoot)
if (-not $resolvedTemp.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe temporary path: $resolvedTemp"
}

New-Item -ItemType Directory -Path $resolvedTemp | Out-Null
$archive = Join-Path $resolvedTemp "ffmpeg.zip"
$expanded = Join-Path $resolvedTemp "expanded"

try {
    Write-Host "Downloading FFmpeg from $DownloadUrl"
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $archive
    Expand-Archive -LiteralPath $archive -DestinationPath $expanded

    $binFolder = Get-ChildItem -LiteralPath $expanded -Directory -Recurse |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "ffmpeg.exe") } |
        Select-Object -First 1
    if (-not $binFolder) {
        throw "ffmpeg.exe was not found in the downloaded archive"
    }

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    foreach ($name in "ffmpeg.exe", "ffprobe.exe", "ffplay.exe") {
        $source = Join-Path $binFolder.FullName $name
        if (Test-Path -LiteralPath $source -PathType Leaf) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $Destination $name) -Force
        }
    }

    & (Join-Path $Destination "ffmpeg.exe") -version | Select-Object -First 1
    Write-Host "FFmpeg installed in $Destination"
}
finally {
    if (Test-Path -LiteralPath $resolvedTemp) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
    }
}
