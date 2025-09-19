"""
RepositoryService - Handles all .gitblend directory operations and metadata management.

This service centralizes all the logic for:
- .gitblend directory initialization and validation
- Commit metadata reading/writing
- Signature file management
- Path resolution and file operations
"""

import json
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import bpy


class RepositoryService:
    """Service for managing .gitblend repository operations."""
    
    @staticmethod
    def get_project_paths() -> Tuple[Optional[Path], Optional[Path]]:
        """Get project directory and .gitblend directory paths."""
        if not bpy.data.filepath:
            return None, None
        
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        gitblend_dir = project_dir / ".gitblend"
        
        return project_dir, gitblend_dir
    
    @staticmethod
    def is_initialized() -> bool:
        """Check if .gitblend repository is initialized."""
        project_dir, gitblend_dir = RepositoryService.get_project_paths()
        return gitblend_dir is not None and gitblend_dir.exists()
    
    @staticmethod
    def validate_can_operate() -> Tuple[bool, str]:
        """Validate that operations can be performed on the repository."""
        if not bpy.data.filepath:
            return False, "Blend file must be saved before using Git Blend"
        
        project_dir, gitblend_dir = RepositoryService.get_project_paths()
        if not gitblend_dir.exists():
            return False, "Git Blend not initialized. Run initialize first."
        
        return True, ""
    
    @staticmethod
    def initialize_repository(commit_message: str = "Initial commit") -> Tuple[bool, str, Optional[Dict]]:
        """
        Initialize a new .gitblend repository.
        
        Returns:
            Tuple of (success, message, commit_data)
        """
        project_dir, gitblend_dir = RepositoryService.get_project_paths()
        
        if not project_dir:
            return False, "Blend file must be saved before initializing Git Blend", None
        
        if gitblend_dir.exists():
            return False, "Git Blend already initialized", None
        
        try:
            # Create .gitblend directory
            gitblend_dir.mkdir()
            
            # Generate initial commit
            timestamp = datetime.now().isoformat()
            current_time = int(time.time())
            
            commit_data = {
                "hash": RepositoryService._generate_commit_hash(current_time, commit_message),
                "timestamp": timestamp,
                "message": commit_message,
                "parent": None,
                "delta_export": False,
                "changed_blocks": []
            }
            
            # Save initial metadata
            metadata = {
                "version": 1,
                "commits": [commit_data]
            }
            
            RepositoryService.save_metadata(metadata)
            
            return True, f"Git Blend initialized with commit: {commit_data['hash'][:8]}", commit_data
            
        except Exception as e:
            return False, f"Failed to initialize: {str(e)}", None
    
    @staticmethod
    def load_metadata() -> Optional[Dict]:
        """Load commit metadata from commits.json."""
        try:
            project_dir, gitblend_dir = RepositoryService.get_project_paths()
            if not gitblend_dir:
                return None
            
            metadata_file = gitblend_dir / "commits.json"
            if not metadata_file.exists():
                return None
            
            with metadata_file.open('r') as f:
                return json.load(f)
        except Exception:
            return None
    
    @staticmethod
    def save_metadata(metadata: Dict) -> bool:
        """Save commit metadata to commits.json."""
        try:
            project_dir, gitblend_dir = RepositoryService.get_project_paths()
            if not gitblend_dir:
                return False
            
            metadata_file = gitblend_dir / "commits.json"
            with metadata_file.open('w') as f:
                json.dump(metadata, f, indent=2)
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_latest_commit_hash() -> Optional[str]:
        """Get the hash of the latest commit."""
        metadata = RepositoryService.load_metadata()
        if not metadata:
            return None
        
        commits = metadata.get('commits', [])
        if not commits:
            return None
        
        return commits[-1]['hash']
    
    @staticmethod
    def add_commit_to_metadata(commit_data: Dict) -> bool:
        """Add a new commit to the metadata."""
        metadata = RepositoryService.load_metadata()
        if not metadata:
            metadata = {"version": 1, "commits": []}
        
        if 'commits' not in metadata:
            metadata['commits'] = []
        
        metadata['commits'].append(commit_data)
        return RepositoryService.save_metadata(metadata)
    
    @staticmethod
    def save_signature_file(commit_hash: str, signature: Dict) -> bool:
        """Save a signature file for a commit."""
        try:
            project_dir, gitblend_dir = RepositoryService.get_project_paths()
            if not gitblend_dir:
                return False
            
            signature_file = gitblend_dir / f"{commit_hash}_signature.json"
            with signature_file.open('w') as f:
                json.dump(signature, f, indent=2)
            return True
        except Exception:
            return False
    
    @staticmethod
    def load_signature_file(commit_hash: str) -> Optional[Dict]:
        """Load a signature file for a commit."""
        try:
            project_dir, gitblend_dir = RepositoryService.get_project_paths()
            if not gitblend_dir:
                return None
            
            signature_file = gitblend_dir / f"{commit_hash}_signature.json"
            if not signature_file.exists():
                return None
            
            with signature_file.open('r') as f:
                return json.load(f)
        except Exception:
            return None
    
    @staticmethod
    def get_commit_file_path(commit_hash: str) -> Optional[Path]:
        """Get the path to a commit's .blend file."""
        project_dir, gitblend_dir = RepositoryService.get_project_paths()
        if not gitblend_dir:
            return None
        
        commit_file = gitblend_dir / f"{commit_hash}.blend"
        return commit_file if commit_file.exists() else None
    
    @staticmethod
    def cleanup_temp_files() -> None:
        """Clean up temporary files in .gitblend directory."""
        try:
            project_dir, gitblend_dir = RepositoryService.get_project_paths()
            if not gitblend_dir:
                return
            
            # Clean up temporary signature files
            temp_signature_file = gitblend_dir / "temp_current_signature.json"
            if temp_signature_file.exists():
                temp_signature_file.unlink()
        except Exception:
            pass  # Silently ignore cleanup errors
    
    @staticmethod
    def find_commit_by_hash(commit_hash: str) -> Optional[Dict]:
        """Find a commit by its hash."""
        metadata = RepositoryService.load_metadata()
        if not metadata:
            return None
        
        commits = metadata.get('commits', [])
        for commit in commits:
            if commit['hash'] == commit_hash:
                return commit
        
        return None
    
    @staticmethod
    def get_all_commits() -> List[Dict]:
        """Get all commits from metadata."""
        metadata = RepositoryService.load_metadata()
        if not metadata:
            return []
        
        return metadata.get('commits', [])
    
    @staticmethod
    def build_commit_chain(target_commit_hash: str) -> List[Dict]:
        """Build the chain of commits from initial to target for reconstruction."""
        all_commits = RepositoryService.get_all_commits()
        if not all_commits:
            return []
        
        # Find target commit
        target_commit = None
        for commit in all_commits:
            if commit['hash'] == target_commit_hash:
                target_commit = commit
                break
        
        if not target_commit:
            return []
        
        # Create a lookup map for faster parent finding
        commit_map = {commit['hash']: commit for commit in all_commits}
        
        # Build chain backwards from target to initial
        chain = []
        current = target_commit
        
        while current:
            chain.append(current)
            
            # Find parent
            parent_hash = current.get('parent')
            if parent_hash and parent_hash in commit_map:
                current = commit_map[parent_hash]
            else:
                # Reached initial commit or broken chain
                break
        
        # Reverse to get chronological order (initial -> target)
        chain.reverse()
        return chain
    
    @staticmethod
    def _generate_commit_hash(timestamp: int, message: str, parent_hash: Optional[str] = None) -> str:
        """Generate SHA-256 hash for commit."""
        content = f"{timestamp}_{message}_{parent_hash or ''}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    @staticmethod
    def generate_new_commit_hash(message: str, parent_hash: Optional[str] = None) -> str:
        """Generate a new commit hash with current timestamp."""
        current_time = int(time.time())
        return RepositoryService._generate_commit_hash(current_time, message, parent_hash)