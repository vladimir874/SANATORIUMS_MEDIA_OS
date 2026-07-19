[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $HotelcutArgs
)

$ErrorActionPreference = "Stop"
$candidates = [System.Collections.Generic.List[string]]::new()

if ($env:HOTELCUT_PYTHON) {
    $candidates.Add($env:HOTELCUT_PYTHON)
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $candidates.Add($pythonCommand.Source)
}

if ($env:USERPROFILE) {
    $candidates.Add(
        (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
    )
}

$python = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
if (-not $python) {
    Write-Error "Python 3.10-3.12 не найден. Укажите полный путь в HOTELCUT_PYTHON."
    exit 2
}

$src = Join-Path $PSScriptRoot "src"
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$src$([System.IO.Path]::PathSeparator)$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $src
}

& $python -m hotelcut @HotelcutArgs
exit $LASTEXITCODE
