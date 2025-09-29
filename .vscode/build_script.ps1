# PowerShell script to zip the Blender addon using manifest ID and version
param(
    [string]$OutputDir = "dist",
    [switch]$Clean
)

# Function to parse TOML-like file for specific keys
function Get-ManifestValue {
    param(
        [string]$FilePath,
        [string]$Key
    )
    
    if (-not (Test-Path $FilePath)) {
        throw "Manifest file not found: $FilePath"
    }
    
    $content = Get-Content $FilePath
    foreach ($line in $content) {
        if ($line -match "^\s*$Key\s*=\s*`"(.+?)`"") {
            return $matches[1]
        }
    }
    
    throw "Key '$Key' not found in manifest file"
}

try {
    # Get the script directory and project root
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = Split-Path -Parent $ScriptDir
    $ManifestPath = Join-Path $ProjectRoot "blender_manifest.toml"
    
    Write-Host "Project Root: $ProjectRoot" -ForegroundColor Green
    Write-Host "Manifest Path: $ManifestPath" -ForegroundColor Green
    
    # Read manifest values
    $AddonId = Get-ManifestValue -FilePath $ManifestPath -Key "id"
    $AddonVersion = Get-ManifestValue -FilePath $ManifestPath -Key "version"
    
    Write-Host "Addon ID: $AddonId" -ForegroundColor Cyan
    Write-Host "Addon Version: $AddonVersion" -ForegroundColor Cyan
    
    # Ensure output directory exists
    $ResolvedOutputDir = if ([System.IO.Path]::IsPathRooted($OutputDir)) {
        $OutputDir
    } else {
        Join-Path $ProjectRoot $OutputDir
    }
    
    if (-not (Test-Path $ResolvedOutputDir)) {
        Write-Host "Creating output directory: $ResolvedOutputDir" -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $ResolvedOutputDir -Force | Out-Null
    }
    
    # Create output filename
    $ZipFileName = "${AddonId}_${AddonVersion}.zip"
    $OutputPath = Join-Path $ResolvedOutputDir $ZipFileName
    
    Write-Host "Output Path: $OutputPath" -ForegroundColor Yellow
    
    # Remove existing zip if it exists
    if (Test-Path $OutputPath) {
        Write-Host "Removing existing zip file..." -ForegroundColor Yellow
        Remove-Item $OutputPath -Force
    }
    
    # Define files and folders to exclude
    $ExcludePatterns = @(
        "__pycache__",
        "*.pyc",
        ".git",
        ".gitignore",
        ".vscode",
        "*.zip",
        ".DS_Store",
        "Thumbs.db",
        "test_*",
        "*.log",
        "README.md",
        ".venv"
    )
    
    # Get all files in the project root, excluding the patterns
    Write-Host "Collecting files to zip..." -ForegroundColor Green
    $FilesToZip = Get-ChildItem -Path $ProjectRoot -Recurse -File | Where-Object {
        $file = $_
        $shouldExclude = $false
        
        foreach ($pattern in $ExcludePatterns) {
            $relativePath = $file.FullName.Substring($ProjectRoot.Length + 1)
            if ($relativePath -like "*$pattern*") {
                $shouldExclude = $true
                break
            }
        }
        
        -not $shouldExclude
    }
    
    Write-Host "Found $($FilesToZip.Count) files to include" -ForegroundColor Cyan
    
    # Create temporary directory for staging
    $TempDir = Join-Path $env:TEMP "blender_addon_build_$(Get-Random)"
    $StagingDir = Join-Path $TempDir $AddonId
    New-Item -ItemType Directory -Path $StagingDir -Force | Out-Null
    
    try {
        # Copy files to staging directory maintaining structure
        Write-Host "Copying files to staging directory..." -ForegroundColor Green
        foreach ($file in $FilesToZip) {
            $relativePath = $file.FullName.Substring($ProjectRoot.Length + 1)
            $destPath = Join-Path $StagingDir $relativePath
            $destDir = Split-Path -Parent $destPath
            
            if (-not (Test-Path $destDir)) {
                New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            }
            
            Copy-Item $file.FullName $destPath
        }
        
        # Create the zip file
        Write-Host "Creating zip file..." -ForegroundColor Green
        Compress-Archive -Path "$StagingDir\*" -DestinationPath $OutputPath -Force
        
        # Verify the zip was created
        if (Test-Path $OutputPath) {
            $zipSize = (Get-Item $OutputPath).Length
            $zipSizeMB = [math]::Round($zipSize / 1MB, 2)
            Write-Host "Successfully created: $ZipFileName ($zipSizeMB MB)" -ForegroundColor Green
            
            # Show zip contents
            Write-Host "`nZip contents:" -ForegroundColor Cyan
            $zipContents = Get-ChildItem -Path $StagingDir -Recurse -File
            foreach ($item in $zipContents) {
                $relativePath = $item.FullName.Substring($StagingDir.Length + 1)
                Write-Host "  $relativePath" -ForegroundColor DarkGray
            }
        } else {
            throw "Failed to create zip file"
        }
        
    } finally {
        # Clean up temporary directory
        if (Test-Path $TempDir) {
            Remove-Item $TempDir -Recurse -Force
        }
    }
    
} catch {
    Write-Error "Build failed: $($_.Exception.Message)"
    exit 1
}

Write-Host "`nBuild completed successfully!" -ForegroundColor Green