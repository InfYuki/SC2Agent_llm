[CmdletBinding()]
param([switch]$Apply)

$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\', '/')
$projectPrefix = $projectRoot + [System.IO.Path]::DirectorySeparatorChar
$cacheNames = @('__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache')
$sourceRoots = @('bot', 'tools', 'tests', 'configs', 'docs', 'scripts')
$candidates = [System.Collections.Generic.List[System.IO.DirectoryInfo]]::new()

function Assert-ProjectPath([string]$Path) {
    $absolutePath = [System.IO.Path]::GetFullPath($Path)
    if (-not $absolutePath.StartsWith($projectPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing path outside the project: $absolutePath"
    }
    return $absolutePath
}

function Find-CacheDirectories([string]$Path) {
    foreach ($directory in Get-ChildItem -LiteralPath $Path -Directory -Force) {
        if ($directory.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { continue }
        $null = Assert-ProjectPath $directory.FullName
        if ($directory.Name -in $cacheNames) {
            $candidates.Add($directory)
        } else {
            Find-CacheDirectories $directory.FullName
        }
    }
}

# Never scan dependencies, Git internals, local setup, artifacts, or training data.
foreach ($directory in Get-ChildItem -LiteralPath $projectRoot -Directory -Force) {
    if ($directory.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { continue }
    if ($directory.Name -in $cacheNames) { $candidates.Add($directory) }
}
foreach ($sourceRoot in $sourceRoots) {
    $scanPath = Join-Path $projectRoot $sourceRoot
    if (Test-Path -LiteralPath $scanPath -PathType Container) {
        $scanItem = Get-Item -LiteralPath $scanPath -Force
        if (-not ($scanItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
            Find-CacheDirectories $scanPath
        }
    }
}

$removedFiles = 0
$removedBytes = [long]0
$results = @(
    foreach ($candidate in $candidates) {
        $targetPath = Assert-ProjectPath $candidate.FullName
        $entries = @(Get-ChildItem -LiteralPath $targetPath -Force -Recurse)
        if (@($entries | Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint }).Count) {
            throw "Refusing cache containing a reparse point: $targetPath"
        }
        $files = @($entries | Where-Object { -not $_.PSIsContainer })
        $bytes = [long](($files | Measure-Object -Property Length -Sum).Sum)
        if ($Apply) {
            # The absolute target and every entry have been checked before recursion.
            Remove-Item -LiteralPath $targetPath -Force -Recurse
        }
        $removedFiles += $files.Count
        $removedBytes += $bytes
        [PSCustomObject]@{ path = $targetPath; files = $files.Count; bytes = $bytes }
    }
)
[PSCustomObject]@{
    mode = $(if ($Apply) { 'applied' } else { 'dry-run' })
    directories = $results
    total_files = $removedFiles
    total_bytes = $removedBytes
} | ConvertTo-Json -Depth 4
