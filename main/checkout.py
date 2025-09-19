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
            
            # Load target commit signature to know what complete scene should look like
            target_signature = self._load_commit_signature(gitblend_dir, target_commit['hash'])
            if not target_signature:
                self.report({'ERROR'}, "Could not load target commit signature")
                return {'CANCELLED'}
            
            # Use signature-based reconstruction instead of clearing everything
            print(f"[GitBlend] Reconstructing scene to match target signature")
            self._reconstruct_scene_from_signature(gitblend_dir, commit_chain, target_signature)
            
            # Simple cleanup of any remaining orphaned data blocks
            print(f"[GitBlend] Final cleanup of orphaned data blocks")
            self._cleanup_orphaned_data()
            
            # Verify and fix all node group references after checkout
            print(f"[GitBlend] Verifying and fixing node group references")
            self._verify_and_fix_node_group_references()
            
            # Debug: Print final node group status
            self._debug_node_group_status()
            
            # Resolve duplications and dangling pointers for node groups
            print(f"[GitBlend] Resolving node group duplications and dangling pointers")
            self._resolve_duplications_and_dangling_pointers()
            
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
    
    def _load_commit_signature(self, gitblend_dir, commit_hash):
        """Load the signature file for a commit to know what objects should exist"""
        signature_file = gitblend_dir / f"{commit_hash}_signature.json"
        
        if not signature_file.exists():
            print(f"[GitBlend] Warning: No signature file found for commit {commit_hash[:8]}")
            return None
        
        try:
            with signature_file.open('r') as f:
                signature = json.load(f)
            print(f"[GitBlend] Loaded signature for commit {commit_hash[:8]}: "
                  f"{len(signature.get('objects', {}))} objects expected")
            return signature
        except Exception as e:
            print(f"[GitBlend] Error loading signature for commit {commit_hash[:8]}: {e}")
            return None
    
    def _reconstruct_scene_from_signature(self, gitblend_dir, commit_chain, target_signature):
        """Reconstruct scene to match target signature by intelligently applying commits"""
        print(f"[GitBlend] Starting signature-based reconstruction")
        
        # Clear current scene first
        self._clear_scene()
        
        # Step 1: Apply the initial commit (full state)
        initial_commit = commit_chain[0]
        initial_file = gitblend_dir / f"{initial_commit['hash']}.blend"
        print(f"[GitBlend] Loading initial commit: {initial_commit['hash'][:8]}")
        self._load_full_commit(str(initial_file))
        
        # Step 2: Apply each delta commit
        for i, commit in enumerate(commit_chain[1:], 1):
            commit_file = gitblend_dir / f"{commit['hash']}.blend"
            is_delta = commit.get('delta_export', False)
            print(f"[GitBlend] Applying delta commit {i}/{len(commit_chain)-1}: {commit['hash'][:8]}")
            
            if is_delta:
                self._apply_delta_commit(str(commit_file))
            else:
                # If it's not a delta (shouldn't happen after initial), treat as full
                self._load_full_commit(str(commit_file))
        
        # Step 3: Ensure final scene matches target signature exactly
        self._enforce_signature_compliance(gitblend_dir, commit_chain, target_signature)
    
    def _enforce_signature_compliance(self, gitblend_dir, commit_chain, target_signature):
        """Ensure the final scene exactly matches what the target signature expects"""
        print(f"[GitBlend] Enforcing signature compliance")
        
        expected_objects = set(target_signature.get('objects', {}).keys())
        current_objects = set(obj.name for obj in bpy.data.objects)
        
        print(f"[GitBlend] Expected: {len(expected_objects)} objects")
        print(f"[GitBlend] Current: {len(current_objects)} objects")
        
        # Handle missing objects
        missing_objects = expected_objects - current_objects
        if missing_objects:
            print(f"[GitBlend] Missing {len(missing_objects)} objects: {missing_objects}")
            self._restore_missing_objects_from_chain(gitblend_dir, commit_chain, missing_objects)
        
        # Handle extra objects  
        extra_objects = current_objects - expected_objects
        if extra_objects:
            print(f"[GitBlend] Removing {len(extra_objects)} extra objects: {extra_objects}")
            self._remove_extra_objects(extra_objects)
        
        # Verify final state
        final_objects = set(obj.name for obj in bpy.data.objects)
        if final_objects == expected_objects:
            print(f"[GitBlend] ✓ Scene successfully reconstructed with {len(final_objects)} objects")
        else:
            missing_final = expected_objects - final_objects
            extra_final = final_objects - expected_objects
            print(f"[GitBlend] ⚠ Scene reconstruction incomplete:")
            if missing_final:
                print(f"[GitBlend]   Still missing: {missing_final}")
            if extra_final:
                print(f"[GitBlend]   Still extra: {extra_final}")
    
    def _restore_missing_objects_from_chain(self, gitblend_dir, commit_chain, missing_objects):
        """Try to restore missing objects by searching through all commits in the chain"""
        print(f"[GitBlend] Searching commit chain for {len(missing_objects)} missing objects")
        
        # Search commits in reverse order (newest first) to get latest versions
        for commit in reversed(commit_chain):
            if not missing_objects:  # All objects found
                break
                
            commit_file = gitblend_dir / f"{commit['hash']}.blend"
            if not commit_file.exists():
                continue
            
            try:
                # Check what objects are available in this commit
                with bpy.data.libraries.load(str(commit_file), link=False) as (data_from, data_to):
                    available_objects = set(data_from.objects)
                    found_objects = missing_objects & available_objects
                    
                    if found_objects:
                        print(f"[GitBlend] Found {len(found_objects)} objects in commit {commit['hash'][:8]}")
                        
                        # Load the found objects
                        data_to.objects = list(found_objects)
                        data_to.meshes = data_from.meshes
                        data_to.materials = data_from.materials  
                        data_to.images = data_from.images
                        data_to.actions = data_from.actions
                        data_to.node_groups = data_from.node_groups
                
                # Link found objects to scene
                scene = bpy.context.scene
                for obj in data_to.objects:
                    if obj and obj.name not in scene.objects:
                        scene.collection.objects.link(obj)
                        print(f"[GitBlend] Restored missing object: {obj.name}")
                        missing_objects.discard(obj.name)
                        
            except Exception as e:
                print(f"[GitBlend] Error searching commit {commit['hash'][:8]}: {e}")
        
        if missing_objects:
            print(f"[GitBlend] Warning: Could not find {len(missing_objects)} objects in commit chain: {missing_objects}")
    
    def _apply_final_commit_with_signature(self, blend_file_path, target_signature, is_delta=False):
        """Apply final commit ensuring complete scene matches signature"""
        print(f"[GitBlend] Applying final commit with signature verification")
        
        # First apply the commit normally
        self._apply_commit_data(blend_file_path, is_delta)
        
        # Now ensure scene matches the expected signature
        expected_objects = set(target_signature.get('objects', {}).keys())
        current_objects = set(obj.name for obj in bpy.data.objects)
        
        print(f"[GitBlend] Expected objects: {len(expected_objects)}")
        print(f"[GitBlend] Current objects: {len(current_objects)}")
        
        # Find missing objects that should exist but don't
        missing_objects = expected_objects - current_objects
        if missing_objects:
            print(f"[GitBlend] Missing objects detected: {missing_objects}")
            self._restore_missing_objects(blend_file_path, missing_objects, target_signature)
        
        # Find extra objects that exist but shouldn't
        extra_objects = current_objects - expected_objects  
        if extra_objects:
            print(f"[GitBlend] Extra objects detected: {extra_objects}")
            self._remove_extra_objects(extra_objects)
    
    def _restore_missing_objects(self, blend_file_path, missing_objects, target_signature):
        """Restore objects that are missing from the current scene"""
        print(f"[GitBlend] Attempting to restore {len(missing_objects)} missing objects")
        
        # Try to load missing objects from the commit file
        try:
            with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
                # Only load missing objects that are available in the commit file
                available_objects = set(data_from.objects)
                objects_to_load = list(missing_objects & available_objects)
                
                if objects_to_load:
                    data_to.objects = objects_to_load
                    # Also load their dependencies
                    data_to.meshes = data_from.meshes
                    data_to.materials = data_from.materials
                    data_to.images = data_from.images
                    data_to.actions = data_from.actions
                    data_to.node_groups = data_from.node_groups
                    
                    print(f"[GitBlend] Loaded {len(objects_to_load)} missing objects from commit")
            
            # Ensure loaded node groups are properly linked
            self._ensure_node_group_linking()
            
            # Link restored objects to scene
            scene = bpy.context.scene
            for obj in data_to.objects:
                if obj and obj.name not in scene.objects:
                    scene.collection.objects.link(obj)
                    print(f"[GitBlend] Restored object to scene: {obj.name}")
                    missing_objects.discard(obj.name)
        
        except Exception as e:
            print(f"[GitBlend] Error restoring missing objects: {e}")
        
        # For objects still missing, they might need to be reconstructed from earlier commits
        still_missing = missing_objects - set(obj.name for obj in bpy.data.objects)
        if still_missing:
            print(f"[GitBlend] Warning: Could not restore {len(still_missing)} objects: {still_missing}")
    
    def _remove_extra_objects(self, extra_objects):
        """Remove objects that shouldn't exist according to the target signature"""
        print(f"[GitBlend] Removing {len(extra_objects)} extra objects")
        
        scene = bpy.context.scene
        for obj_name in extra_objects:
            obj = bpy.data.objects.get(obj_name)
            if obj:
                try:
                    # Remove from scene
                    if obj.name in scene.objects:
                        scene.collection.objects.unlink(obj)
                    # Remove from data
                    bpy.data.objects.remove(obj, do_unlink=True)
                    print(f"[GitBlend] Removed extra object: {obj_name}")
                except Exception as e:
                    print(f"[GitBlend] Warning: Failed to remove extra object {obj_name}: {e}")
    
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
        
        # Clear orphaned node groups
        for node_group in list(bpy.data.node_groups):
            if node_group.users == 0:
                bpy.data.node_groups.remove(node_group, do_unlink=True)
        
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
                data_to.node_groups = data_from.node_groups
            
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
            delta_node_groups = []
            
            with bpy.data.libraries.load(blend_file_path, link=False, assets_only=False) as (data_from, data_to):
                # Don't load anything yet, just inspect what's available
                delta_objects = list(data_from.objects)
                delta_meshes = list(data_from.meshes) 
                delta_materials = list(data_from.materials)
                delta_images = list(data_from.images)
                delta_texts = list(data_from.texts)
                delta_actions = list(data_from.actions)
                delta_node_groups = list(data_from.node_groups)
            
            print(f"[GitBlend] Delta contains: {len(delta_objects)} objects, {len(delta_meshes)} meshes, "
                  f"{len(delta_materials)} materials, {len(delta_images)} images, {len(delta_node_groups)} node groups")
            
            # IMPORTANT: For mesh-only deltas, we need to preserve existing objects
            # Store object-mesh relationships before replacing meshes
            object_mesh_map = {}
            if delta_meshes and not delta_objects:
                # This is a mesh-only delta (like editing vertices)
                for obj in bpy.data.objects:
                    if obj.type == 'MESH' and obj.data and obj.data.name in delta_meshes:
                        object_mesh_map[obj.data.name] = obj
                        print(f"[GitBlend] Preserving object '{obj.name}' for mesh '{obj.data.name}'")
            
            # Now surgically replace each type of data block
            # Process in order: data blocks first, then objects that depend on them
            # IMPORTANT: Node groups should be processed before objects to ensure proper linking
            if delta_node_groups:
                self._replace_data_blocks(blend_file_path, 'node_groups', delta_node_groups)
            if delta_meshes:
                self._replace_data_blocks_with_preservation(blend_file_path, 'meshes', delta_meshes, object_mesh_map)
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
                data_to.node_groups = data_from.node_groups
            
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
            'actions': bpy.data.actions,
            'node_groups': bpy.data.node_groups
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
        elif data_type == 'node_groups':
            # Store node group relationships for proper restoration
            dependent_relationships = self._store_node_group_relationships(block_names)
        
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
        
        elif data_type == 'node_groups':
            # Restore node group references
            self._restore_node_group_relationships(target_data, dependent_relationships)
        
        print(f"[GitBlend] Added {len(target_data)} new {data_type}")
    
    def _store_node_group_relationships(self, node_group_names):
        """Store all relationships that reference the specified node groups"""
        relationships = {}
        
        for node_group_name in node_group_names:
            relationships[node_group_name] = {
                'geometry_modifiers': [],
                'material_nodes': [],
                'compositor_nodes': [],
                'nested_node_groups': []
            }
            
            # Find geometry modifiers using this node group
            for obj in bpy.data.objects:
                if hasattr(obj, 'modifiers'):
                    for i, modifier in enumerate(obj.modifiers):
                        if modifier.type == 'NODES' and hasattr(modifier, 'node_group'):
                            if modifier.node_group and modifier.node_group.name == node_group_name:
                                relationships[node_group_name]['geometry_modifiers'].append({
                                    'object_name': obj.name,
                                    'modifier_index': i,
                                    'modifier_name': modifier.name
                                })
            
            # Find material nodes using this node group
            for material in bpy.data.materials:
                if material.use_nodes and material.node_tree:
                    for node in material.node_tree.nodes:
                        if node.type == 'GROUP' and hasattr(node, 'node_tree'):
                            if node.node_tree and node.node_tree.name == node_group_name:
                                relationships[node_group_name]['material_nodes'].append({
                                    'material_name': material.name,
                                    'node_name': node.name
                                })
            
            # Find compositor nodes using this node group
            if bpy.context.scene.use_nodes and bpy.context.scene.node_tree:
                for node in bpy.context.scene.node_tree.nodes:
                    if node.type == 'GROUP' and hasattr(node, 'node_tree'):
                        if node.node_tree and node.node_tree.name == node_group_name:
                            relationships[node_group_name]['compositor_nodes'].append({
                                'node_name': node.name
                            })
            
            # Find other node groups using this node group
            for other_node_group in bpy.data.node_groups:
                if other_node_group.name != node_group_name:
                    for node in other_node_group.nodes:
                        if node.type == 'GROUP' and hasattr(node, 'node_tree'):
                            if node.node_tree and node.node_tree.name == node_group_name:
                                relationships[node_group_name]['nested_node_groups'].append({
                                    'parent_node_group_name': other_node_group.name,
                                    'node_name': node.name
                                })
        
        return relationships
    
    def _restore_node_group_relationships(self, loaded_node_groups, relationships):
        """Restore node group references after loading new node groups"""
        print(f"[GitBlend] Restoring node group relationships for {len(loaded_node_groups)} node groups")
        
        for node_group in loaded_node_groups:
            if not node_group or node_group.name not in relationships:
                continue
                
            node_group_name = node_group.name
            refs = relationships[node_group_name]
            
            # Restore geometry modifier references
            for ref in refs['geometry_modifiers']:
                obj = bpy.data.objects.get(ref['object_name'])
                if obj and hasattr(obj, 'modifiers'):
                    if ref['modifier_index'] < len(obj.modifiers):
                        modifier = obj.modifiers[ref['modifier_index']]
                        if modifier.type == 'NODES' and hasattr(modifier, 'node_group'):
                            modifier.node_group = node_group
                            print(f"[GitBlend] Restored geometry modifier reference: {obj.name}.{modifier.name} -> {node_group_name}")
                    else:
                        # Try to find by name if index is out of range
                        modifier = next((m for m in obj.modifiers if m.name == ref['modifier_name']), None)
                        if modifier and modifier.type == 'NODES':
                            modifier.node_group = node_group
                            print(f"[GitBlend] Restored geometry modifier reference by name: {obj.name}.{modifier.name} -> {node_group_name}")
            
            # Restore material node references
            for ref in refs['material_nodes']:
                material = bpy.data.materials.get(ref['material_name'])
                if material and material.use_nodes and material.node_tree:
                    node = material.node_tree.nodes.get(ref['node_name'])
                    if node and node.type == 'GROUP' and hasattr(node, 'node_tree'):
                        node.node_tree = node_group
                        print(f"[GitBlend] Restored material node reference: {material.name}.{node.name} -> {node_group_name}")
            
            # Restore compositor node references
            if bpy.context.scene.use_nodes and bpy.context.scene.node_tree:
                for ref in refs['compositor_nodes']:
                    node = bpy.context.scene.node_tree.nodes.get(ref['node_name'])
                    if node and node.type == 'GROUP' and hasattr(node, 'node_tree'):
                        node.node_tree = node_group
                        print(f"[GitBlend] Restored compositor node reference: {node.name} -> {node_group_name}")
            
            # Restore nested node group references
            for ref in refs['nested_node_groups']:
                parent_node_group = bpy.data.node_groups.get(ref['parent_node_group_name'])
                if parent_node_group:
                    node = parent_node_group.nodes.get(ref['node_name'])
                    if node and node.type == 'GROUP' and hasattr(node, 'node_tree'):
                        node.node_tree = node_group
                        print(f"[GitBlend] Restored nested node group reference: {parent_node_group.name}.{node.name} -> {node_group_name}")
    
    def _replace_data_blocks_with_preservation(self, blend_file_path, data_type, block_names, object_mesh_map=None):
        """Surgically replace specific data blocks while preserving object relationships"""
        print(f"[GitBlend] Replacing {len(block_names)} {data_type} with preservation")
        
        # Get the appropriate Blender data collection
        collections_map = {
            'meshes': bpy.data.meshes,
            'materials': bpy.data.materials,
            'images': bpy.data.images,
            'texts': bpy.data.texts,
            'actions': bpy.data.actions,
            'node_groups': bpy.data.node_groups
        }
        
        collection = collections_map.get(data_type)
        if not collection:
            print(f"[GitBlend] Unknown data type: {data_type}")
            return
        
        # For meshes, we need special handling to preserve object references
        if data_type == 'meshes' and object_mesh_map:
            # Load new meshes from delta commit
            loaded_meshes = {}
            with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
                # Load only the specific meshes we want
                data_to.meshes = [name for name in data_from.meshes if name in block_names]
            
            # Store the loaded meshes by name
            for mesh in data_to.meshes:
                if mesh:
                    loaded_meshes[mesh.name] = mesh
                    print(f"[GitBlend] Loaded mesh: {mesh.name}")
            
            # Replace mesh data on existing objects
            for mesh_name, obj in object_mesh_map.items():
                if mesh_name in loaded_meshes:
                    old_mesh = obj.data
                    new_mesh = loaded_meshes[mesh_name]
                    
                    # Preserve mesh name if it changed
                    if new_mesh.name != mesh_name:
                        # Rename to avoid conflicts
                        new_mesh.name = mesh_name
                    
                    # Update object's mesh reference
                    obj.data = new_mesh
                    print(f"[GitBlend] Updated object '{obj.name}' with new mesh '{new_mesh.name}'")
                    
                    # Remove old mesh if it has no users
                    if old_mesh and old_mesh.users == 0:
                        bpy.data.meshes.remove(old_mesh, do_unlink=True)
                        print(f"[GitBlend] Removed old mesh: {old_mesh.name}")
            
            # Handle any meshes that weren't linked to objects (shouldn't happen in mesh-only delta)
            for mesh_name in block_names:
                if mesh_name not in object_mesh_map and mesh_name in loaded_meshes:
                    print(f"[GitBlend] Warning: Mesh '{mesh_name}' has no associated object")
                    # The mesh is already loaded, it will be available if an object needs it
        else:
            # Fall back to original replacement method for non-mesh data blocks
            self._replace_data_blocks(blend_file_path, data_type, block_names)
    
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
        
        # Clean up node groups with no users
        removed_node_groups = 0
        for node_group in list(bpy.data.node_groups):
            if node_group.users == 0 and not node_group.use_fake_user:
                bpy.data.node_groups.remove(node_group, do_unlink=True)
                removed_node_groups += 1
        
        print(f"[GitBlend] Cleanup complete: removed {removed_meshes} meshes, "
              f"{removed_materials} materials, {removed_images} images, "
              f"{removed_actions} actions, {removed_texts} texts, "
              f"{removed_node_groups} node groups")
    
    def _verify_and_fix_node_group_references(self):
        """Verify and fix all node group references after checkout to ensure proper linking"""
        print(f"[GitBlend] Verifying node group references...")
        
        fixed_count = 0
        
        # Fix geometry modifier references
        for obj in bpy.data.objects:
            if hasattr(obj, 'modifiers'):
                for modifier in obj.modifiers:
                    if modifier.type == 'NODES' and hasattr(modifier, 'node_group'):
                        if modifier.node_group is None:
                            # Try to find a matching node group by name
                            # This can happen if the node group was loaded but the reference was lost
                            potential_name = f"Geometry Nodes"  # Default geometry nodes name
                            if potential_name in bpy.data.node_groups:
                                modifier.node_group = bpy.data.node_groups[potential_name]
                                print(f"[GitBlend] Fixed geometry modifier reference: {obj.name}.{modifier.name}")
                                fixed_count += 1
        
        # Fix material node references
        for material in bpy.data.materials:
            if material.use_nodes and material.node_tree:
                for node in material.node_tree.nodes:
                    if node.type == 'GROUP' and hasattr(node, 'node_tree'):
                        if node.node_tree is None:
                            # Try to find by node name or look for compatible node groups
                            for node_group in bpy.data.node_groups:
                                if node_group.type == 'SHADER':
                                    # For now, assign the first available shader node group
                                    # In practice, you might want more sophisticated matching
                                    node.node_tree = node_group
                                    print(f"[GitBlend] Fixed material node reference: {material.name}.{node.name}")
                                    fixed_count += 1
                                    break
        
        # Fix compositor node references
        if bpy.context.scene.use_nodes and bpy.context.scene.node_tree:
            for node in bpy.context.scene.node_tree.nodes:
                if node.type == 'GROUP' and hasattr(node, 'node_tree'):
                    if node.node_tree is None:
                        # Try to find by compatible compositor node groups
                        for node_group in bpy.data.node_groups:
                            if node_group.type == 'COMPOSITING':
                                node.node_tree = node_group
                                print(f"[GitBlend] Fixed compositor node reference: {node.name}")
                                fixed_count += 1
                                break
        
        print(f"[GitBlend] Node group reference verification complete. Fixed {fixed_count} broken references.")
    
    def _ensure_node_group_linking(self):
        """Ensure node groups are properly linked after loading"""
        print(f"[GitBlend] Ensuring node group linking...")
        
        # Force update of all node trees to ensure proper linking
        try:
            # Update material node trees
            for material in bpy.data.materials:
                if material.use_nodes and material.node_tree:
                    material.node_tree.update_tag()
            
            # Update geometry node modifiers
            for obj in bpy.data.objects:
                if hasattr(obj, 'modifiers'):
                    for modifier in obj.modifiers:
                        if modifier.type == 'NODES' and modifier.node_group:
                            modifier.node_group.update_tag()
            
            # Update compositor
            if bpy.context.scene.use_nodes and bpy.context.scene.node_tree:
                bpy.context.scene.node_tree.update_tag()
            
            print(f"[GitBlend] Node group linking update complete")
        except Exception as e:
            print(f"[GitBlend] Warning: Failed to update node group linking: {e}")
    
    def _resolve_duplications_and_dangling_pointers(self):
        """Resolve possible duplication and dangling pointers after checkout"""
        print(f"[GitBlend] Resolving duplications and dangling pointers...")
        
        # Resolve node group references in materials
        self._resolve_material_node_group_references()
        
        # Resolve node group references in geometry modifiers
        self._resolve_geometry_modifier_node_group_references()
        
        # Resolve node group references in compositor
        self._resolve_compositor_node_group_references()
        
        # Remove duplicate node groups (same name but different objects)
        self._remove_duplicate_node_groups()
        
        print(f"[GitBlend] Duplication and pointer resolution complete")
    
    def _resolve_material_node_group_references(self):
        """Resolve node group references in material node trees"""
        for material in bpy.data.materials:
            if material.use_nodes and material.node_tree:
                for node in material.node_tree.nodes:
                    if node.type == 'GROUP' and hasattr(node, 'node_tree'):
                        if node.node_tree and node.node_tree.name in bpy.data.node_groups:
                            # Ensure the node references the correct node group by name
                            correct_node_group = bpy.data.node_groups.get(node.node_tree.name)
                            if correct_node_group and node.node_tree != correct_node_group:
                                print(f"[GitBlend] Fixing material node group reference: {material.name} -> {correct_node_group.name}")
                                node.node_tree = correct_node_group
    
    def _resolve_geometry_modifier_node_group_references(self):
        """Resolve node group references in geometry modifiers"""
        for obj in bpy.data.objects:
            if hasattr(obj, 'modifiers'):
                for modifier in obj.modifiers:
                    if modifier.type == 'NODES' and hasattr(modifier, 'node_group'):
                        if modifier.node_group and modifier.node_group.name in bpy.data.node_groups:
                            # Ensure the modifier references the correct node group by name
                            correct_node_group = bpy.data.node_groups.get(modifier.node_group.name)
                            if correct_node_group and modifier.node_group != correct_node_group:
                                print(f"[GitBlend] Fixing geometry modifier node group reference: {obj.name}.{modifier.name} -> {correct_node_group.name}")
                                modifier.node_group = correct_node_group
    
    def _resolve_compositor_node_group_references(self):
        """Resolve node group references in compositor node trees"""
        if bpy.context.scene.use_nodes and bpy.context.scene.node_tree:
            for node in bpy.context.scene.node_tree.nodes:
                if node.type == 'GROUP' and hasattr(node, 'node_tree'):
                    if node.node_tree and node.node_tree.name in bpy.data.node_groups:
                        # Ensure the node references the correct node group by name
                        correct_node_group = bpy.data.node_groups.get(node.node_tree.name)
                        if correct_node_group and node.node_tree != correct_node_group:
                            print(f"[GitBlend] Fixing compositor node group reference: {correct_node_group.name}")
                            node.node_tree = correct_node_group
    
    def _remove_duplicate_node_groups(self):
        """Remove duplicate node groups with the same name"""
        node_group_names = {}
        duplicates_to_remove = []
        
        for node_group in bpy.data.node_groups:
            if node_group.name in node_group_names:
                # Found a duplicate - mark for removal
                duplicates_to_remove.append(node_group)
                print(f"[GitBlend] Found duplicate node group: {node_group.name}")
            else:
                node_group_names[node_group.name] = node_group
        
        # Remove duplicates
        for duplicate in duplicates_to_remove:
            try:
                # First reassign any references to the duplicate to the original
                original = node_group_names[duplicate.name]
                self._reassign_node_group_references(duplicate, original)
                
                # Then remove the duplicate
                bpy.data.node_groups.remove(duplicate, do_unlink=True)
                print(f"[GitBlend] Removed duplicate node group: {duplicate.name}")
            except Exception as e:
                print(f"[GitBlend] Warning: Failed to remove duplicate node group {duplicate.name}: {e}")
    
    def _reassign_node_group_references(self, old_node_group, new_node_group):
        """Reassign all references from old_node_group to new_node_group"""
        # Check material nodes
        for material in bpy.data.materials:
            if material.use_nodes and material.node_tree:
                for node in material.node_tree.nodes:
                    if node.type == 'GROUP' and hasattr(node, 'node_tree') and node.node_tree == old_node_group:
                        node.node_tree = new_node_group
        
        # Check geometry modifier nodes
        for obj in bpy.data.objects:
            if hasattr(obj, 'modifiers'):
                for modifier in obj.modifiers:
                    if modifier.type == 'NODES' and hasattr(modifier, 'node_group') and modifier.node_group == old_node_group:
                        modifier.node_group = new_node_group
        
        # Check compositor nodes
        if bpy.context.scene.use_nodes and bpy.context.scene.node_tree:
            for node in bpy.context.scene.node_tree.nodes:
                if node.type == 'GROUP' and hasattr(node, 'node_tree') and node.node_tree == old_node_group:
                    node.node_tree = new_node_group
        
        # Check node groups within other node groups
        for node_group in bpy.data.node_groups:
            if node_group != old_node_group and node_group != new_node_group:
                for node in node_group.nodes:
                    if node.type == 'GROUP' and hasattr(node, 'node_tree') and node.node_tree == old_node_group:
                        node.node_tree = new_node_group
    
    def _debug_node_group_status(self):
        """Debug function to print current node group status"""
        print(f"[GitBlend] === Node Group Status Debug ===")
        print(f"Total node groups: {len(bpy.data.node_groups)}")
        
        for node_group in bpy.data.node_groups:
            print(f"  - {node_group.name} (type: {node_group.type}, users: {node_group.users})")
        
        print(f"Geometry modifier references:")
        for obj in bpy.data.objects:
            if hasattr(obj, 'modifiers'):
                for modifier in obj.modifiers:
                    if modifier.type == 'NODES':
                        ng_name = modifier.node_group.name if modifier.node_group else "None"
                        print(f"  - {obj.name}.{modifier.name} -> {ng_name}")
        
        print(f"Material node references:")
        for material in bpy.data.materials:
            if material.use_nodes and material.node_tree:
                for node in material.node_tree.nodes:
                    if node.type == 'GROUP':
                        ng_name = node.node_tree.name if node.node_tree else "None"
                        print(f"  - {material.name}.{node.name} -> {ng_name}")
        
        print(f"[GitBlend] === End Node Group Debug ===")


def register():
    bpy.utils.register_class(GITBLEND_OT_Checkout)


def unregister():
    bpy.utils.unregister_class(GITBLEND_OT_Checkout)