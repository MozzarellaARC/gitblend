$ErrorActionPreference = 'Stop'

# Resolve repo root to the folder containing this script
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$ManifestPath = Join-Path $ScriptDir 'blender_manifest.toml'
if (!(Test-Path -LiteralPath $ManifestPath)) {
	throw "blender_manifest.toml not found at $ManifestPath"
}

$manifestText = Get-Content -LiteralPath $ManifestPath -Raw

function Get-TomlStringValue {
	param(
		[Parameter(Mandatory=$true)][string]$Text,
		[Parameter(Mandatory=$true)][string]$Key
	)
	# Matches lines like: key = "value"
	$escapedKey = [regex]::Escape($Key)
	$pattern = '^\s*' + $escapedKey + '\s*=\s*"([^"]+)"'
	$m = [regex]::Match($Text, $pattern, [System.Text.RegularExpressions.RegexOptions]::Multiline)
	if ($m.Success) { return $m.Groups[1].Value }
	return $null
}

$id = Get-TomlStringValue -Text $manifestText -Key 'id'
$version = Get-TomlStringValue -Text $manifestText -Key 'version'

if ([string]::IsNullOrWhiteSpace($id)) {
	throw "Unable to parse 'id' from blender_manifest.toml"
}
if ([string]::IsNullOrWhiteSpace($version)) {
	throw "Unable to parse 'version' from blender_manifest.toml"
}

$zipName = "$id-$version.zip"

## Always output to ./dist
$destDir = Join-Path $ScriptDir 'dist'
if (!(Test-Path -LiteralPath $destDir)) {
	New-Item -ItemType Directory -Path $destDir -Force | Out-Null
}

$destPath = Join-Path $destDir $zipName

# Collect items to include
$includeNames = @('locales', 'main', 'pref', 'utils', '__init__.py', 'blender_manifest.toml')
$pathsToZip = @()
foreach ($name in $includeNames) {
	$p = Join-Path $ScriptDir $name
	if (Test-Path -LiteralPath $p) {
		$pathsToZip += $p
	} else {
		Write-Warning "Skipping missing item: $name"
	}
}

if ($pathsToZip.Count -eq 0) {
	throw "No files found to package."
}

if (Test-Path -LiteralPath $destPath) {
	Remove-Item -LiteralPath $destPath -Force
}

Compress-Archive -LiteralPath $pathsToZip -DestinationPath $destPath -CompressionLevel Optimal

Write-Host "Created package: $destPath"

