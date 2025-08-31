# Directory-agnostic Blender add-on packager
# - Finds the nearest ancestor containing both __init__.py and blender_manifest.toml
# - Reads id and version from blender_manifest.toml
# - Creates dist/<id>-<version>.zip with only: __init__.py, blender_manifest.toml, and the main folder

$ErrorActionPreference = 'Stop'

function Find-AddonRoot {
	param(
		[string]$StartPath
	)
	$dir = (Resolve-Path -Path $StartPath).Path
	if ((Get-Item $dir) -isnot [System.IO.DirectoryInfo]) {
		$dir = (Get-Item $dir).Directory.FullName
	}
	while ($true) {
		$initPath = Join-Path $dir '__init__.py'
		$manifestPath = Join-Path $dir 'blender_manifest.toml'
		if ((Test-Path -Path $initPath) -and (Test-Path -Path $manifestPath)) {
			return $dir
		}
		$parent = [System.IO.Directory]::GetParent($dir)
		if ($null -eq $parent) { break }
		$dir = $parent.FullName
	}
	return $null
}

function Get-TomlStringValue {
	param(
		[Parameter(Mandatory)] [string]$TomlContent,
		[Parameter(Mandatory)] [string]$Key
	)
	# Matches: key = "value" or key = 'value' at the start of a line
	$pattern = '(?m)^\s*' + [Regex]::Escape($Key) + '\s*=\s*([''"])(?<val>.*?)\1\s*(?:#.*)?$'
	$match = [Regex]::Match($TomlContent, $pattern)
	if ($match.Success) { return $match.Groups['val'].Value.Trim() }
	return $null
}

try {
	$start = Get-Location
	$root = Find-AddonRoot -StartPath $start.Path
	if (-not $root) {
		throw "Could not find a directory containing both __init__.py and blender_manifest.toml starting from '$($start.Path)'."
	}

	$manifestPath = Join-Path $root 'blender_manifest.toml'
	if (-not (Test-Path $manifestPath)) { throw "Missing blender_manifest.toml at '$root'" }
	$toml = Get-Content -Path $manifestPath -Raw -ErrorAction Stop

	$id = Get-TomlStringValue -TomlContent $toml -Key 'id'
	$version = Get-TomlStringValue -TomlContent $toml -Key 'version'

	if ([string]::IsNullOrWhiteSpace($id)) { throw "Could not parse 'id' from blender_manifest.toml" }
	if ([string]::IsNullOrWhiteSpace($version)) { throw "Could not parse 'version' from blender_manifest.toml" }

	# Output zip at the same level as blender_manifest.toml (project root)
	$zipName = "$id-$version.zip"
	$zipPath = Join-Path $root $zipName
	if (Test-Path $zipPath) { Remove-Item -Path $zipPath -Force }

	$items = @('blender_manifest.toml', '__init__.py')
	$mainDir = Join-Path $root 'main'
	if (Test-Path $mainDir) { $items += 'main' } else { Write-Host "Warning: 'main' folder not found at root; only top-level files will be packaged." -ForegroundColor Yellow }

	Push-Location $root
	try {
		# Only include the specified paths from the root
		Compress-Archive -Path $items -DestinationPath $zipPath
	}
	finally {
		Pop-Location
	}

	Write-Host "Created: $zipPath" -ForegroundColor Green
}
catch {
	Write-Error $_
	exit 1
}

