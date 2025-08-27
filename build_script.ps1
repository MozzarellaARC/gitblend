param(
  [Parameter(Position=0)]
  [string]$Destination,
  [switch]$Overwrite
)

$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$root = $root.TrimEnd('\\')

# Read manifest and compute default destination name as <id>-<version>.zip
$manifestPath = Join-Path $root 'blender_manifest.toml'
if (-not (Test-Path -LiteralPath $manifestPath)) {
  throw "blender_manifest.toml not found at $manifestPath"
}
$manifestRaw = Get-Content -LiteralPath $manifestPath -Raw

function Get-TomlStringValue([string]$text, [string]$key) {
  # PowerShell uses doubled quotes inside a double-quoted string; backslashes are literal
  $pattern = "(?m)^\s*" + [regex]::Escape($key) + "\s*=\s*(?:'(?<v>[^']*)'|""(?<v>[^""]*)"")\s*$"
  $m = [regex]::Match($text, $pattern)
  if ($m.Success) { return $m.Groups['v'].Value } else { return $null }
}

$manifestId = Get-TomlStringValue -text $manifestRaw -key 'id'
$manifestVersion = Get-TomlStringValue -text $manifestRaw -key 'version'
if (-not $manifestId) { throw "Couldn't read 'id' from blender_manifest.toml" }
if (-not $manifestVersion) { throw "Couldn't read 'version' from blender_manifest.toml" }

function Format-FileName([string]$name) {
  $invalid = [regex]::Escape([string]::Join('', [IO.Path]::GetInvalidFileNameChars()))
  $s = [regex]::Replace($name, "[$invalid]", '-')
  $s = $s.Trim().TrimEnd('.', ' ')
  if (-not $s) { return 'addon' }
  return $s
}

if (-not $Destination -or [string]::IsNullOrWhiteSpace($Destination)) {
  $base = (Format-FileName $manifestId) + '-' + (Format-FileName $manifestVersion)
  $Destination = "$base.zip"
}

$zipPath = Join-Path $root $Destination

if (Test-Path -LiteralPath $zipPath) {
  if ($Overwrite) {
    Remove-Item -LiteralPath $zipPath -Force
  } else {
    Write-Error "Destination '$zipPath' already exists. Use -Overwrite to replace."
  }
}

Push-Location -LiteralPath $root
try {
  $toArchive = New-Object System.Collections.Generic.List[string]

  foreach ($f in @('__init__.py','blender_manifest.toml')) {
    if (Test-Path -LiteralPath $f) {
      [void]$toArchive.Add($f)
    } else {
      Write-Warning "Skipping missing file: $f"
    }
  }

  if (Test-Path -LiteralPath 'main') {
    Get-ChildItem -LiteralPath 'main' -Recurse -File -Force |
  Where-Object { $_.FullName -notlike '*\__pycache__\*' } |
      ForEach-Object {
        $rel = $_.FullName.Substring($root.Length + 1)
        [void]$toArchive.Add($rel)
      }
  } else {
    Write-Warning "Folder 'main' not found."
  }

  if ($toArchive.Count -eq 0) {
    throw "No files to archive."
  }

  Compress-Archive -Path $toArchive -DestinationPath $zipPath
  Write-Host "Created: $zipPath"
}
finally {
  Pop-Location
}
