<#
PowerShell build/packaging script for the Blender add-on.
Creates a zip named <id>-<version>.zip using values from blender_manifest.toml.
Output is written to a top-level dist/ directory.
It excludes development and cache artifacts (.git, .vscode, dist, __pycache__, *.pyc, existing zips, tests/demo folders).

Run (from repo root):
	pwsh -ExecutionPolicy Bypass -File .vscode/build_script.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Section($Title) {
	Write-Host "`n==== $Title ====\n" -ForegroundColor Cyan
}

try {
	Write-Section 'Resolve paths'
	$ScriptDir = Split-Path -Parent $PSCommandPath
	$RepoRoot  = Resolve-Path (Join-Path $ScriptDir '..')
	Push-Location $RepoRoot

	$ManifestPath = Join-Path $RepoRoot 'blender_manifest.toml'
	if (-not (Test-Path $ManifestPath)) { throw "Manifest not found: $ManifestPath" }

	Write-Section 'Parse manifest (id + version)'
	$manifestContent = Get-Content -Raw $ManifestPath
	if ($manifestContent -notmatch '(?m)^\s*id\s*=\s*"([^"]+)"') { throw 'Could not parse id from manifest' }
	$AddonId = $Matches[1]
	if ($manifestContent -notmatch '(?m)^\s*version\s*=\s*"([^"]+)"') { throw 'Could not parse version from manifest' }
	$AddonVersion = $Matches[1]
	Write-Host "Id: $AddonId" -ForegroundColor Green
	Write-Host "Version: $AddonVersion" -ForegroundColor Green

	Write-Section 'Prepare output paths'
	$DistDir = Join-Path $RepoRoot 'dist'
	if (-not (Test-Path $DistDir)) { New-Item -ItemType Directory -Path $DistDir | Out-Null }
	$ZipName = "$AddonId-$AddonVersion.zip"
	$ZipPath = Join-Path $DistDir $ZipName
	$ChecksumPath = "$ZipPath.sha256"

	if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
	if (Test-Path $ChecksumPath) { Remove-Item $ChecksumPath -Force }

	Write-Section 'Stage files'
	$Staging = Join-Path ([IO.Path]::GetTempPath()) ("gitblend_pkg_" + [guid]::NewGuid().ToString('N'))
	New-Item -ItemType Directory -Path $Staging | Out-Null

	# Relative path helper
	function Get-RelativePath([string]$Full) { return $Full.Substring($RepoRoot.Path.Length + 1) }

	$excludeDirPatterns = @(
		'^\.git($|[\/])'
		'^\.vscode($|[\/])'
		'^dist($|[\/])'
		'^__pycache__($|[\/])'
		'^test_blend_demo($|[\/])'
	)
	$excludeFilePatterns = @(
		'\.pyc$'
		'\.pyo$'
		'\.zip$'
		'^\.gitignore$'
		'^\.gitattributes$'
	)

	$AllFiles = Get-ChildItem -Recurse -File | Where-Object {
		$rel = Get-RelativePath $_.FullName
		if ($rel -eq '.vscode/build_script.ps1') { return $false } # don't include the build script itself
		foreach ($pat in $excludeDirPatterns) { if ($rel -match $pat) { return $false } }
		foreach ($pat in $excludeFilePatterns) { if ($rel -match $pat) { return $false } }
		return $true
	}

	foreach ($file in $AllFiles) {
		$rel = Get-RelativePath $file.FullName
		$dest = Join-Path $Staging $rel
		$destDir = Split-Path -Parent $dest
		if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
		Copy-Item $file.FullName $dest -Force
	}
	Write-Host ("Files staged: " + $AllFiles.Count)

	Write-Section 'Create zip'
	Compress-Archive -Path (Join-Path $Staging '*') -DestinationPath $ZipPath -CompressionLevel Optimal
	Write-Host "Created $ZipPath" -ForegroundColor Green

	Write-Section 'Cleanup staging'
	Remove-Item $Staging -Recurse -Force
	Write-Host 'Done.' -ForegroundColor Cyan
	Write-Host "Artifact: $ZipPath"
	exit 0
}
catch {
	Write-Error $_
	exit 1
}
finally {
	if (Get-Location) { Pop-Location -ErrorAction SilentlyContinue }
}

