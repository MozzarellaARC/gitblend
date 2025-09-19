import bpy  # type: ignore
import json
from pathlib import Path


class GITBLEND_OT_Checkout(bpy.types.Operator):
    bl_idname = "gitblend.checkout"
    bl_label = "Checkout Commit"
    bl_description = "Checkout and restore scene to selected commit"
    bl_options = {'REGISTER', 'UNDO'}
    
    commit_hash: bpy.props.StringProperty(
        name="Commit Hash",
        description="Hash of commit to checkout"
    )
    
    @classmethod
    def poll(cls, context):
        # Can only checkout if blend file is saved and gitblend is initialized
        if not bpy.data.filepath:
            return False
        
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        gitblend_dir = project_dir / ".gitblend"
        
        return gitblend_dir.exists()
    
    def execute(self, context):
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        gitblend_dir = project_dir / ".gitblend"
        metadata_file = gitblend_dir / "commits.json"
        
        # Debug: Print the commit hash we're looking for
        print(f"[GitBlend] Attempting to checkout commit: {self.commit_hash}")
        
        # Validate commit hash is provided
        if not self.commit_hash:
            self.report({'ERROR'}, "No commit hash provided. Please select a commit first.")
            return {'CANCELLED'}
        
        # Validate .gitblend exists
        if not gitblend_dir.exists():
            self.report({'ERROR'}, "Git Blend not initialized")
            return {'CANCELLED'}
        
        # Load metadata
        if not metadata_file.exists():
            self.report({'ERROR'}, "No commits found")
            return {'CANCELLED'}
        
        try:
            with metadata_file.open('r') as f:
                metadata = json.load(f)
            
            commits = metadata.get('commits', [])
            if not commits:
                self.report({'ERROR'}, "No commits found in metadata")
                return {'CANCELLED'}
            
            # Debug: Print available commits
            print(f"[GitBlend] Available commits:")
            for commit in commits:
                print(f"  - {commit.get('hash', 'NO_HASH')[:8]}: {commit.get('message', 'NO_MESSAGE')}")
            
            # Find target commit
            target_commit = None
            for commit in commits:
                if commit['hash'] == self.commit_hash:
                    target_commit = commit
                    break
            
            if not target_commit:
                print(f"[GitBlend] Commit hash '{self.commit_hash}' not found in available commits")
                self.report({'ERROR'}, f"Commit {self.commit_hash[:8]} not found")
                return {'CANCELLED'}
            
            # Build commit chain for delta reconstruction
            commit_chain = self._build_commit_chain(commits, target_commit)
            
            if not commit_chain:
                self.report({'ERROR'}, "Failed to build commit chain")
                return {'CANCELLED'}
            
            # Clear current scene
            self._clear_scene()
            
            # Apply commits in order (initial + deltas for reconstruction)
            print(f"[GitBlend] Reconstructing scene with {len(commit_chain)} commits")
            for i, commit in enumerate(commit_chain):
                commit_file = gitblend_dir / f"{commit['hash']}.blend"
                
                if not commit_file.exists():
                    self.report({'ERROR'}, f"Commit file {commit['hash'][:8]} not found")
                    return {'CANCELLED'}
                
                # Load and apply this commit's data
                is_delta = commit.get('delta_export', False)
                print(f"[GitBlend] Applying commit {i+1}/{len(commit_chain)}: {commit['hash'][:8]} ({'delta' if is_delta else 'full'})")
                self._apply_commit_data(str(commit_file), is_delta)
            
            # Simple cleanup of any remaining orphaned data blocks
            print(f"[GitBlend] Final cleanup of orphaned data blocks")
            self._cleanup_orphaned_data()
            
            # Update UI to show we're on this commit
            props = context.scene.gitblend_props
            props.current_commit = self.commit_hash
            
            # Refresh UI
            from .initialize import populate_ui_from_metadata
            populate_ui_from_metadata(context)
            
            self.report({'INFO'}, f"Checked out commit {self.commit_hash[:8]}: {target_commit['message']}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to checkout: {str(e)}")
            return {'CANCELLED'}
    
    def _build_commit_chain(self, all_commits, target_commit):
        """Build the chain of commits from initial to target for delta reconstruction"""
        chain = []
        current = target_commit
        
        # Create a lookup map for faster parent finding
        commit_map = {commit['hash']: commit for commit in all_commits}
        
        # Build chain backwards from target to initial
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
        
        # Debug: Print the commit chain
        print(f"[GitBlend] Commit chain for reconstruction ({len(chain)} commits):")
        for i, commit in enumerate(chain):
            is_delta = commit.get('delta_export', False)
            print(f"  {i+1}. {commit['hash'][:8]}: {commit['message']} ({'delta' if is_delta else 'full'})")
        
        return chain
    
    def _clear_scene(self):
        """Clear all data blocks from the current scene"""
        # Store viewport settings before clearing
        viewport_settings = self._store_viewport_settings()
        
        # Clear in reverse dependency order to avoid issues
        # First clear objects (they reference other data)
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        
        # Clear orphaned meshes
        for mesh in list(bpy.data.meshes):
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh, do_unlink=True)
        
        # Clear orphaned materials
        for mat in list(bpy.data.materials):
            if mat.users == 0:
                bpy.data.materials.remove(mat, do_unlink=True)
        
        # Clear orphaned images
        for img in list(bpy.data.images):
            if img.users == 0:
                bpy.data.images.remove(img, do_unlink=True)
        
        # Clear orphaned actions
        for action in list(bpy.data.actions):
            if action.users == 0:
                bpy.data.actions.remove(action, do_unlink=True)
        
        # Clear texts (usually safe to clear all)
        for text in list(bpy.data.texts):
            if text.users == 0:
                bpy.data.texts.remove(text, do_unlink=True)
        
        # Restore viewport settings
        self._restore_viewport_settings(viewport_settings)
    
    def _store_viewport_settings(self):
        """Store current viewport settings to restore after clearing"""
        settings = {}
        
        # Store 3D viewport settings if available
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces[0]
                settings['viewport'] = {
                    'view_location': space.region_3d.view_location.copy() if hasattr(space, 'region_3d') else None,
                    'view_rotation': space.region_3d.view_rotation.copy() if hasattr(space, 'region_3d') else None,
                    'view_distance': space.region_3d.view_distance if hasattr(space, 'region_3d') else None,
                }
                break
        
        return settings
    
    def _restore_viewport_settings(self, settings):
        """Restore viewport settings after clearing"""
        if 'viewport' not in settings:
            return
        
        viewport_settings = settings['viewport']
        
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces[0]
                if hasattr(space, 'region_3d'):
                    region_3d = space.region_3d
                    if viewport_settings['view_location']:
                        region_3d.view_location = viewport_settings['view_location']
                    if viewport_settings['view_rotation']:
                        region_3d.view_rotation = viewport_settings['view_rotation']
                    if viewport_settings['view_distance']:
                        region_3d.view_distance = viewport_settings['view_distance']
                break
    
    def _apply_commit_data(self, blend_file_path, is_delta=False):
        """Apply data from a commit file - full replace for initial, surgical replace for deltas"""
        print(f"[GitBlend] Applying commit data from: {blend_file_path} (delta: {is_delta})")
        
        if not is_delta:
            # Initial commit: simple full load
            self._load_full_commit(blend_file_path)
        else:
            # Delta commit: surgical replacement
            self._apply_delta_commit(blend_file_path)
    
    def _load_full_commit(self, blend_file_path):
        """Load initial commit data (full state)"""
        print(f"[GitBlend] Loading full commit state")
        
        try:
            with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
                # Load all data blocks for initial commit
                data_to.objects = data_from.objects
                data_to.meshes = data_from.meshes
                data_to.materials = data_from.materials
                data_to.images = data_from.images
                data_to.texts = data_from.texts
                data_to.actions = data_from.actions
            
            # Link all objects to the scene
            scene = bpy.context.scene
            for obj in data_to.objects:
                if obj and obj.name not in scene.objects:
                    scene.collection.objects.link(obj)
            
            print(f"[GitBlend] Loaded {len(data_to.objects)} objects from initial commit")
                  
        except Exception as e:
            print(f"[GitBlend] Error loading full commit: {e}")
            raise
    
    def _apply_delta_commit(self, blend_file_path):
        """Apply delta commit by surgically replacing changed data blocks"""
        print(f"[GitBlend] Applying delta commit")
        
        try:
            # First, identify what data blocks are in this delta commit
            delta_objects = []
            delta_meshes = []
            delta_materials = []
            delta_images = []
            delta_texts = []
            delta_actions = []
            
            with bpy.data.libraries.load(blend_file_path, link=False, assets_only=False) as (data_from, data_to):
                # Don't load anything yet, just inspect what's available
                delta_objects = list(data_from.objects)
                delta_meshes = list(data_from.meshes) 
                delta_materials = list(data_from.materials)
                delta_images = list(data_from.images)
                delta_texts = list(data_from.texts)
                delta_actions = list(data_from.actions)
            
            print(f"[GitBlend] Delta contains: {len(delta_objects)} objects, {len(delta_meshes)} meshes, "
                  f"{len(delta_materials)} materials, {len(delta_images)} images")
            
            # Now surgically replace each type of data block
            # Process in order: data blocks first, then objects that depend on them
            if delta_meshes:
                self._replace_data_blocks(blend_file_path, 'meshes', delta_meshes)
            if delta_materials:
                self._replace_data_blocks(blend_file_path, 'materials', delta_materials)
            if delta_images:
                self._replace_data_blocks(blend_file_path, 'images', delta_images)
            if delta_texts:
                self._replace_data_blocks(blend_file_path, 'texts', delta_texts)
            if delta_actions:
                self._replace_data_blocks(blend_file_path, 'actions', delta_actions)
            
            # Process objects last, after their dependencies are in place
            if delta_objects:
                self._replace_objects(blend_file_path, delta_objects)
                
        except Exception as e:
            print(f"[GitBlend] Error applying delta commit: {e}")
            # Print more details for debugging
            import traceback
            traceback.print_exc()
            raise
    
    def _replace_objects(self, blend_file_path, object_names):
        """Surgically replace objects from delta commit"""
        print(f"[GitBlend] Replacing {len(object_names)} objects")
        
        scene = bpy.context.scene
        
        # Remove existing objects with these names from scene and data
        removed_objects = []
        for obj_name in object_names:
            existing_obj = bpy.data.objects.get(obj_name)
            if existing_obj:
                try:
                    # Remove from scene first
                    if existing_obj.name in scene.objects:
                        scene.collection.objects.unlink(existing_obj)
                    # Remove from data
                    bpy.data.objects.remove(existing_obj, do_unlink=True)
                    removed_objects.append(obj_name)
                    print(f"[GitBlend] Removed existing object: {obj_name}")
                except Exception as e:
                    print(f"[GitBlend] Warning: Failed to remove object {obj_name}: {e}")
        
        # Load new objects from delta commit
        try:
            with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
                # Only load the specific objects we want
                data_to.objects = [name for name in data_from.objects if name in object_names]
                # Also load their dependencies
                data_to.meshes = data_from.meshes
                data_to.materials = data_from.materials
                data_to.images = data_from.images
                data_to.actions = data_from.actions
            
            # Link new objects to scene
            added_objects = []
            for obj in data_to.objects:
                if obj:
                    try:
                        scene.collection.objects.link(obj)
                        added_objects.append(obj.name)
                        print(f"[GitBlend] Added new object: {obj.name}")
                    except Exception as e:
                        print(f"[GitBlend] Warning: Failed to link object {obj.name}: {e}")
            
            print(f"[GitBlend] Successfully replaced {len(added_objects)} objects")
            
        except Exception as e:
            print(f"[GitBlend] Error loading objects from delta commit: {e}")
            raise
    
    def _replace_data_blocks(self, blend_file_path, data_type, block_names):
        """Surgically replace specific data blocks (meshes, materials, etc.)"""
        print(f"[GitBlend] Replacing {len(block_names)} {data_type}")
        
        # Get the appropriate Blender data collection
        collections_map = {
            'meshes': bpy.data.meshes,
            'materials': bpy.data.materials,
            'images': bpy.data.images,
            'texts': bpy.data.texts,
            'actions': bpy.data.actions
        }
        
        collection = collections_map.get(data_type)
        if not collection:
            print(f"[GitBlend] Unknown data type: {data_type}")
            return
        
        # Store relationships using object NAMES instead of object references
        dependent_relationships = {}
        if data_type in ['meshes', 'materials']:
            for obj in bpy.data.objects:
                if data_type == 'meshes' and obj.type == 'MESH' and obj.data and obj.data.name in block_names:
                    dependent_relationships[obj.data.name] = obj.name
                elif data_type == 'materials' and hasattr(obj.data, 'materials') and obj.data:
                    for i, mat in enumerate(obj.data.materials):
                        if mat and mat.name in block_names:
                            if mat.name not in dependent_relationships:
                                dependent_relationships[mat.name] = []
                            dependent_relationships[mat.name].append((obj.name, i))
        
        # Remove existing data blocks
        for block_name in block_names:
            existing_block = collection.get(block_name)
            if existing_block:
                collection.remove(existing_block, do_unlink=True)
                print(f"[GitBlend] Removed existing {data_type[:-1]}: {block_name}")
        
        # Load new data blocks from delta commit
        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            # Load only the specific data blocks we want
            source_collection = getattr(data_from, data_type)
            target_collection = getattr(data_to, data_type)
            target_collection[:] = [name for name in source_collection if name in block_names]
        
        # Restore references using object names (safer)
        target_data = getattr(data_to, data_type)
        if data_type == 'meshes':
            for mesh in target_data:
                if mesh and mesh.name in dependent_relationships:
                    obj_name = dependent_relationships[mesh.name]
                    obj = bpy.data.objects.get(obj_name)
                    if obj:  # Check if object still exists
                        obj.data = mesh
                        print(f"[GitBlend] Restored mesh reference: {obj.name} -> {mesh.name}")
                    else:
                        print(f"[GitBlend] Warning: Object {obj_name} no longer exists, skipping mesh reference")
        
        elif data_type == 'materials':
            for material in target_data:
                if material and material.name in dependent_relationships:
                    for obj_name, slot_index in dependent_relationships[material.name]:
                        obj = bpy.data.objects.get(obj_name)
                        if obj and hasattr(obj.data, 'materials') and obj.data:  # Check if object and data still exist
                            try:
                                if slot_index < len(obj.data.materials):
                                    obj.data.materials[slot_index] = material
                                    print(f"[GitBlend] Restored material reference: {obj.name}[{slot_index}] -> {material.name}")
                                else:
                                    print(f"[GitBlend] Warning: Material slot {slot_index} no longer exists on {obj.name}")
                            except Exception as e:
                                print(f"[GitBlend] Warning: Failed to restore material reference for {obj.name}: {e}")
                        else:
                            print(f"[GitBlend] Warning: Object {obj_name} no longer exists, skipping material reference")
        
        print(f"[GitBlend] Added {len(target_data)} new {data_type}")
    
    def _cleanup_orphaned_data(self):
        """Clean up orphaned data blocks after reconstruction"""
        print(f"[GitBlend] Cleaning up orphaned data blocks...")
        
        # Clean up meshes with no users
        removed_meshes = 0
        for mesh in list(bpy.data.meshes):
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh, do_unlink=True)
                removed_meshes += 1
        
        # Clean up materials with no users
        removed_materials = 0
        for mat in list(bpy.data.materials):
            if mat.users == 0 and not mat.use_fake_user:
                bpy.data.materials.remove(mat, do_unlink=True)
                removed_materials += 1
        
        # Clean up images with no users
        removed_images = 0
        for img in list(bpy.data.images):
            if img.users == 0 and not img.use_fake_user:
                bpy.data.images.remove(img, do_unlink=True)
                removed_images += 1
        
        # Clean up actions with no users
        removed_actions = 0
        for action in list(bpy.data.actions):
            if action.users == 0 and not action.use_fake_user:
                bpy.data.actions.remove(action, do_unlink=True)
                removed_actions += 1
        
        # Clean up texts with no users
        removed_texts = 0
        for text in list(bpy.data.texts):
            if text.users == 0:
                bpy.data.texts.remove(text, do_unlink=True)
                removed_texts += 1
        
        print(f"[GitBlend] Cleanup complete: removed {removed_meshes} meshes, "
              f"{removed_materials} materials, {removed_images} images, "
              f"{removed_actions} actions, {removed_texts} texts")


def register():
    bpy.utils.register_class(GITBLEND_OT_Checkout)


def unregister():
    bpy.utils.unregister_class(GITBLEND_OT_Checkout)