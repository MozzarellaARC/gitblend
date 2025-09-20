# Git Blend Checkout System

The checkout system can reconstruct any commit state using git-like hashes. Here's how it works:

## Commit Structure

Each commit now contains git-like information:

```python
commit_data = {
    "commit": "a1b2c3d4e5f6...",    # Commit hash
    "tree": "f9e8d7c6b5a4...",      # Tree hash (state of all data)
    "parent": "1234567890ab...",     # Parent commit hash
    "data_blocks": {...},           # Serialized data blocks
    "blend_file": "a1b2c3d4.blend", # Exported blend file
    "timestamp": 1726849200.0,      # Commit timestamp
    "message": "Added new mesh",     # Commit message
    "changes": {...}                # What changed
}
```

## Checkout Operations

### 1. Checkout by Full Hash
```python
bpy.ops.gitblend.checkout(commit_hash="a1b2c3d4e5f6789...")
```

### 2. Checkout by Partial Hash (7+ characters)
```python
bpy.ops.gitblend.checkout(commit_hash="a1b2c3d")
```

### 3. Checkout HEAD (latest commit)
```python
bpy.ops.gitblend.checkout(commit_hash="HEAD")
```

## Reconstruction Process

1. **Hash Resolution**: Resolves commit reference to full hash
2. **Data Validation**: Validates commit exists in metadata
3. **Scene Clearing**: Safely removes all current data blocks
4. **Data Import**: Imports data blocks from commit's blend file
5. **Tree Validation**: Verifies reconstructed state matches tree hash
6. **Metadata Update**: Updates current_commit to point to checked out commit

## Hash Validation

The system validates reconstruction using tree hashes:

- **Tree Hash**: SHA-256 of all serialized data blocks
- **Commit Hash**: SHA-256 of commit metadata (tree + parent + timestamp + message)
- **Validation**: Ensures reconstructed state matches original tree hash

## Safety Features

- **Clean Checkout**: Completely clears scene before reconstruction
- **Hash Verification**: Validates data integrity using cryptographic hashes
- **Error Handling**: Reports clear error messages for failed operations
- **Partial Hash Support**: Accepts shortened commit hashes (like git)

## Example Usage in Blender

```python
# Initialize repository
bpy.ops.gitblend.initialize()

# Make some changes and commit
bpy.ops.gitblend.commit()  # Creates commit abc123...

# Make more changes and commit
bpy.ops.gitblend.commit()  # Creates commit def456...

# Checkout previous commit
bpy.ops.gitblend.checkout(commit_hash="abc123")

# Checkout latest commit
bpy.ops.gitblend.checkout(commit_hash="HEAD")
```

## Git-like Features

- **Commit Chain**: Each commit references its parent
- **Content Addressing**: Tree hash represents exact data state
- **Partial Hashes**: Can checkout using shortened commit hashes
- **HEAD Reference**: Always points to the latest commit
- **Data Integrity**: Cryptographic validation of all data