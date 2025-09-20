# Git Blend - Core Implementation

## Overview
Git Blend is a version control system for Blender files that provides git-like functionality for managing changes to data blocks including objects, meshes, materials, images, texts, actions, and node groups.

## Architecture

### Core Components

#### 1. Initialize (`main/initialize.py`)
- **Purpose**: Sets up the `.gitblend` directory and creates the initial commit
- **Functionality**:
  - Creates `.gitblend` directory in the same location as the .blend file
  - Exports all data blocks to a `.blend` file using `bpy.data.libraries.write`
  - Serializes data block metadata to JSON with SHA-256 hash keys
  - Creates initial commit metadata in `commits.json`

#### 2. Diffing (`main/diff.py`)
- **Purpose**: Compares current state with stored commits to detect changes
- **Functionality**:
  - Compares objects, meshes, materials, images, texts, actions, and node groups
  - Uses intelligent sampling for large datasets (e.g., mesh vertices)
  - Returns added, modified, and removed items for each category
  - Optimized comparison algorithms for different data types

#### 3. Commit (`main/commit.py`)
- **Purpose**: Creates new commits with delta changes
- **Functionality**:
  - Detects changes using the diffing system
  - Exports only modified/added data blocks (delta approach)
  - Updates commit metadata with changes and timestamps
  - Maintains full state history in JSON format

#### 4. Checkout (`main/checkout.py`)
- **Purpose**: Restores data blocks from specific commits
- **Functionality**:
  - Loads data blocks from stored `.blend` files using `bpy.data.libraries.load`
  - Clears existing data blocks that will be replaced
  - Links objects to the current scene
  - Updates current commit pointer

#### 5. Utilities (`main/utils.py`)
- **Purpose**: Common utility functions for the system
- **Key Functions**:
  - File hashing with SHA-256
  - Data block serialization and sampling
  - Metadata management
  - Directory operations

### UI Components

#### 1. Main Panel (`prefs/panel.py`)
- **Location**: 3D Viewport > Sidebar > Git Blend tab
- **Features**:
  - Initialize button for new repositories
  - Commit button with message dialog
  - Commit history UIList
  - Checkout functionality
  - Status indicators

#### 2. UIList (`GITBLEND_UL_commit_history`)
- **Purpose**: Displays commit history in an organized list
- **Features**:
  - Shows commit messages, hashes, and timestamps
  - Indicates current commit with radio button icon
  - Interactive selection for checkout operations

#### 3. Properties (`main/properties.py`)
- **Purpose**: Blender property groups for storing UI state
- **Components**:
  - `GITBLEND_CommitItem`: Individual commit data
  - `GITBLEND_Properties`: Main property collection
  - Scene-level property registration

## Data Storage Format

### Directory Structure
```
project_folder/
├── project.blend
└── .gitblend/
    ├── commits.json          # Metadata file
    ├── {hash1}.blend         # Initial commit data
    ├── {hash2}.blend         # Delta commit data
    └── ...
```

### Metadata Format (`commits.json`)
```json
{
  "commits": {
    "hash1": {
      "data_blocks": {
        "objects": [...],
        "meshes": [...],
        "materials": [...],
        "images": [...],
        "texts": [...],
        "actions": [...],
        "node_groups": [...]
      },
      "blend_file": "hash1.blend",
      "timestamp": 1234567890,
      "message": "Initial commit",
      "changes": {...}
    }
  },
  "version": 1,
  "current_commit": "hash1"
}
```

## Usage Workflow

### 1. Initialize Repository
```python
# User clicks "Initialize" button
bpy.ops.gitblend.initialize()
```

### 2. Make Changes
- Modify objects, meshes, materials, etc. in Blender
- Changes are automatically detected by the diffing system

### 3. Commit Changes
```python
# User clicks "Commit" button and enters message
bpy.ops.gitblend.commit(message="Added new material")
```

### 4. View History
```python
# Refresh commit list in UI
bpy.ops.gitblend.refresh_commits()
```

### 5. Checkout Previous Version
```python
# Select commit in UIList and checkout
bpy.ops.gitblend.checkout_selected()
```

## Key Features

### Intelligent Data Sampling
- **Mesh Vertices**: Samples up to 1000 vertices for comparison
- **Large Datasets**: Efficient handling of complex scenes
- **Memory Optimization**: Minimal memory footprint for metadata

### Delta Storage
- **Incremental Commits**: Only stores changed data blocks
- **Space Efficiency**: Reduces storage requirements
- **Fast Operations**: Quick commit and checkout operations

### Robust Error Handling
- **File Validation**: Checks for saved .blend files
- **Error Recovery**: Graceful handling of missing files
- **User Feedback**: Clear error messages and status updates

### Cross-Platform Compatibility
- **Path Handling**: Uses `pathlib` for robust path operations
- **Blender Integration**: Compatible with Blender 4.2+
- **File System**: Works with all major operating systems

## Extension Integration

The system is designed as a Blender extension with:
- **Manifest File**: `blender_manifest.toml` for extension metadata
- **Modular Design**: Separate modules for different functionality
- **Clean Registration**: Proper operator and UI registration
- **Uninstall Support**: Complete cleanup on unregistration

This implementation provides a solid foundation for git-like version control within Blender, offering users an intuitive way to manage their project history and collaborate effectively.