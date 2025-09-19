import bpy
import os
import json
import hashlib
import time
import filecmp
from datetime import datetime
from pathlib import Path


class GITBLEND_OT_Commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit current changes to git blend repository"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        # Can only commit if blend file is saved and gitblend is initialized
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
        
        # Validate .gitblend exists
        if not gitblend_dir.exists():
            self.report({'ERROR'}, "Git Blend not initialized. Run initialize first.")
            return {'CANCELLED'}
        
        try:
            # Load existing metadata
            metadata = {}
            if metadata_file.exists():
                with metadata_file.open('r') as f:
                    metadata = json.load(f)
            
            # Get commit message from UI
            props = context.scene.gitblend_props
            commit_message = props.commit_message.strip()
            
            if not commit_message:
                self.report({'ERROR'}, "Commit message is required")
                return {'CANCELLED'}
            
            # Get parent commit hash (latest commit)
            parent_hash = None
            commits = metadata.get('commits', [])
            if commits:
                parent_hash = commits[-1]['hash']
            
            # Detect changes before generating commit
            changes_detected, change_summary, changed_data_blocks = self._detect_changes_and_deltas(gitblend_dir, parent_hash)
            
            if not changes_detected:
                self.report({'INFO'}, "No changes detected - nothing to commit")
                return {'CANCELLED'}
            
            # Generate new commit data
            timestamp = datetime.now().isoformat()
            current_time = int(time.time())
            
            # Generate new commit hash
            new_commit_hash = self._generate_commit_hash(current_time, commit_message, parent_hash)
            
            # Export only the changed data blocks (delta export)
            final_blend_path = gitblend_dir / f"{new_commit_hash}.blend"
            self._export_delta_data_blocks(str(final_blend_path), changed_data_blocks)
            
            # Save signature file for this commit
            signature_file = gitblend_dir / f"{new_commit_hash}_signature.json"
            current_signature = self._generate_data_signature()
            with signature_file.open('w') as f:
                json.dump(current_signature, f, indent=2)
            
            # Clean up temporary signature file if it exists
            temp_signature_file = gitblend_dir / "temp_current_signature.json"
            if temp_signature_file.exists():
                temp_signature_file.unlink()
            
            # Create new commit metadata with change summary and delta info
            changed_block_names = [block.name for block in changed_data_blocks]
            new_commit = {
                "hash": new_commit_hash,
                "timestamp": timestamp,
                "message": commit_message,
                "parent": parent_hash,
                "changes": change_summary,
                "delta_export": True,
                "changed_blocks": changed_block_names[:50]  # Limit to first 50 for metadata size
            }
            
            # Update metadata
            if 'commits' not in metadata:
                metadata['commits'] = []
            if 'version' not in metadata:
                metadata['version'] = 1
            
            metadata['commits'].append(new_commit)
            
            # Save updated metadata
            with metadata_file.open('w') as f:
                json.dump(metadata, f, indent=2)
            
            # Clear commit message
            props.commit_message = ""
            
            # Ensure initialized property is set to True
            props.initialized = True
            
            # Refresh UI
            from .initialize import populate_ui_from_metadata
            populate_ui_from_metadata(context)
            
            # Report with change summary and delta info
            changes_text = ", ".join([f"{count} {type_name}" for type_name, count in change_summary.items() if count > 0])
            blocks_exported = len(changed_data_blocks)
            self.report({'INFO'}, f"Committed: {new_commit_hash[:8]} - {changes_text} ({blocks_exported} blocks exported)")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to commit: {str(e)}")
            return {'CANCELLED'}
    
    def _detect_changes_and_deltas(self, gitblend_dir, parent_hash):
        """Detect changes and return specific changed data blocks for delta export"""
        if not parent_hash:
            # First commit - everything is new, export all
            current_counts = self._get_data_block_counts()
            change_summary = {
                "objects": current_counts.get("objects", 0),
                "meshes": current_counts.get("meshes", 0),
                "materials": current_counts.get("materials", 0),
                "images": current_counts.get("images", 0),
                "texts": current_counts.get("texts", 0),
                "actions": current_counts.get("actions", 0)
            }
            # For first commit, export everything
            all_data_blocks = self._get_all_data_blocks()
            return True, change_summary, all_data_blocks
        
        # Load previous commit to compare
        previous_blend_path = gitblend_dir / f"{parent_hash}.blend"
        if not previous_blend_path.exists():
            # Previous commit file missing, assume changes, export all
            current_counts = self._get_data_block_counts()
            change_summary = {type_name: count for type_name, count in current_counts.items()}
            all_data_blocks = self._get_all_data_blocks()
            return True, change_summary, all_data_blocks
        
        # Create current state signature
        current_signature = self._generate_data_signature()
        
        # Load previous signature if available
        previous_signature_file = gitblend_dir / f"{parent_hash}_signature.json"
        previous_signature = {}
        
        if previous_signature_file.exists():
            try:
                with previous_signature_file.open('r') as f:
                    previous_signature = json.load(f)
            except Exception:
                pass
        
        # Compare signatures to detect specific changes
        changes_detected, change_summary, changed_data_blocks = self._compare_signatures_and_get_deltas(current_signature, previous_signature)
        
        if changes_detected:
            # Save current signature for future comparisons
            current_signature_file = gitblend_dir / f"temp_current_signature.json"
            with current_signature_file.open('w') as f:
                json.dump(current_signature, f, indent=2)
        
        return changes_detected, change_summary, changed_data_blocks
    
    def _generate_data_signature(self):
        """Generate a signature of current data blocks for change detection"""
        signature = {
            "objects": {},
            "meshes": {},
            "materials": {},
            "images": {},
            "texts": {},
            "actions": {}
        }
        
        # Objects signature
        for obj in bpy.data.objects:
            obj_sig = {
                "name": obj.name,
                "type": obj.type,
                "location": [round(x, 6) for x in obj.location] if hasattr(obj, 'location') else None,
                "rotation": [round(x, 6) for x in obj.rotation_euler] if hasattr(obj, 'rotation_euler') else None,
                "scale": [round(x, 6) for x in obj.scale] if hasattr(obj, 'scale') else None,
                "data_name": obj.data.name if obj.data else None,
                "visible": obj.visible_get() if hasattr(obj, 'visible_get') else True,
                "hide_viewport": obj.hide_viewport if hasattr(obj, 'hide_viewport') else False,
                "modifiers_hash": self._calculate_modifiers_hash(obj),
                "constraints_hash": self._calculate_constraints_hash(obj)
            }
            signature["objects"][obj.name] = obj_sig
        
        # Meshes signature
        for mesh in bpy.data.meshes:
            # Calculate geometry hash for detecting vertex-level changes
            geometry_hash = self._calculate_mesh_geometry_hash(mesh)
            
            mesh_sig = {
                "name": mesh.name,
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
                "materials": [mat.name if mat else None for mat in mesh.materials],
                "geometry_hash": geometry_hash  # This will detect vertex position changes
            }
            signature["meshes"][mesh.name] = mesh_sig
        
        # Materials signature
        for mat in bpy.data.materials:
            mat_sig = {
                "name": mat.name,
                "use_nodes": mat.use_nodes,
                "diffuse_color": [round(x, 4) for x in mat.diffuse_color] if hasattr(mat, 'diffuse_color') else None,
                "roughness": round(mat.roughness, 4) if hasattr(mat, 'roughness') else None,
                "metallic": round(mat.metallic, 4) if hasattr(mat, 'metallic') else None,
                "alpha": round(mat.alpha, 4) if hasattr(mat, 'alpha') else None
            }
            
            # Add node tree hash if using nodes
            if mat.use_nodes and mat.node_tree:
                mat_sig["node_tree_hash"] = self._calculate_node_tree_hash(mat.node_tree)
            
            signature["materials"][mat.name] = mat_sig
        
        # Images signature
        for img in bpy.data.images:
            img_sig = {
                "name": img.name,
                "size": list(img.size) if hasattr(img, 'size') else None,
                "filepath": img.filepath if hasattr(img, 'filepath') else None,
                "file_format": img.file_format if hasattr(img, 'file_format') else None
            }
            signature["images"][img.name] = img_sig
        
        # Texts signature
        for text in bpy.data.texts:
            text_sig = {
                "name": text.name,
                "lines_count": len(text.lines) if hasattr(text, 'lines') else 0,
                "content_hash": hashlib.md5(text.as_string().encode()).hexdigest() if hasattr(text, 'as_string') else None
            }
            signature["texts"][text.name] = text_sig
        
        # Actions signature
        for action in bpy.data.actions:
            action_sig = {
                "name": action.name,
                "frame_range": list(action.frame_range) if hasattr(action, 'frame_range') else None,
                "fcurves_count": len(action.fcurves) if hasattr(action, 'fcurves') else 0
            }
            signature["actions"][action.name] = action_sig
        
        return signature
    
    def _calculate_mesh_geometry_hash(self, mesh):
        """Calculate a hash of mesh geometry to detect vertex-level changes"""
        try:
            # Ensure mesh is evaluated (in case it's being modified)
            mesh.calc_loop_triangles()
            
            # Collect vertex coordinates
            vertex_data = []
            for vertex in mesh.vertices:
                # Include vertex position (co) and normal for better change detection
                vertex_data.extend([
                    round(vertex.co.x, 6),  # Round to avoid floating point precision issues
                    round(vertex.co.y, 6),
                    round(vertex.co.z, 6),
                    round(vertex.normal.x, 6),
                    round(vertex.normal.y, 6),
                    round(vertex.normal.z, 6)
                ])
            
            # Include face data for topology changes
            face_data = []
            for poly in mesh.polygons:
                # Include face vertices indices (sorted to be order-independent)
                face_verts = sorted(poly.vertices)
                face_data.extend(face_verts)
                # Include face normal
                face_data.extend([
                    round(poly.normal.x, 6),
                    round(poly.normal.y, 6),
                    round(poly.normal.z, 6)
                ])
            
            # Combine all geometry data and create hash
            geometry_data = vertex_data + face_data
            geometry_string = ','.join(map(str, geometry_data))
            
            return hashlib.md5(geometry_string.encode()).hexdigest()
            
        except Exception as e:
            # If we can't calculate geometry hash, use a basic fallback
            try:
                # Simple fallback: hash vertex count and face count
                simple_data = f"{len(mesh.vertices)}_{len(mesh.polygons)}_{len(mesh.edges)}"
                return hashlib.md5(simple_data.encode()).hexdigest()
            except Exception:
                # Ultimate fallback
                return "unknown"
    
    def _calculate_node_tree_hash(self, node_tree):
        """Calculate a hash of material node tree to detect node changes"""
        try:
            node_data = []
            
            # Collect node information
            for node in node_tree.nodes:
                node_info = [
                    node.name,
                    node.type,
                    str(node.location.x),
                    str(node.location.y)
                ]
                
                # Add input values for nodes with default values
                for input_socket in node.inputs:
                    if hasattr(input_socket, 'default_value'):
                        try:
                            if hasattr(input_socket.default_value, '__iter__'):
                                # Vector/Color values
                                node_info.extend([str(round(x, 4)) for x in input_socket.default_value])
                            else:
                                # Scalar values
                                node_info.append(str(round(input_socket.default_value, 4)))
                        except (TypeError, AttributeError):
                            pass
                
                node_data.extend(node_info)
            
            # Collect link information
            for link in node_tree.links:
                link_info = [
                    link.from_node.name,
                    link.from_socket.name,
                    link.to_node.name,
                    link.to_socket.name
                ]
                node_data.extend(link_info)
            
            # Create hash from all node data
            node_string = ','.join(node_data)
            return hashlib.md5(node_string.encode()).hexdigest()
            
        except Exception:
            # Fallback: basic node count
            try:
                basic_data = f"{len(node_tree.nodes)}_{len(node_tree.links)}"
                return hashlib.md5(basic_data.encode()).hexdigest()
            except Exception:
                return "unknown"
    
    def _calculate_modifiers_hash(self, obj):
        """Calculate a hash of object modifiers to detect modifier changes"""
        try:
            if not hasattr(obj, 'modifiers') or not obj.modifiers:
                return "no_modifiers"
            
            modifier_data = []
            
            for mod in obj.modifiers:
                mod_info = [
                    mod.name,
                    mod.type,
                    str(mod.show_viewport),
                    str(mod.show_render)
                ]
                
                # Add type-specific properties for common modifiers
                if mod.type == 'SUBSURF':
                    mod_info.extend([
                        str(mod.levels),
                        str(mod.render_levels),
                        str(mod.use_limit_surface)
                    ])
                elif mod.type == 'MIRROR':
                    mod_info.extend([
                        str(mod.use_axis[0]), str(mod.use_axis[1]), str(mod.use_axis[2]),
                        str(mod.use_bisect_axis[0]), str(mod.use_bisect_axis[1]), str(mod.use_bisect_axis[2]),
                        str(mod.use_clip),
                        str(mod.merge_threshold)
                    ])
                elif mod.type == 'ARRAY':
                    mod_info.extend([
                        str(mod.count),
                        str(mod.use_relative_offset),
                        str(mod.use_constant_offset),
                        str([round(x, 4) for x in mod.relative_offset_displace]),
                        str([round(x, 4) for x in mod.constant_offset_displace])
                    ])
                elif mod.type == 'SOLIDIFY':
                    mod_info.extend([
                        str(round(mod.thickness, 6)),
                        str(round(mod.offset, 6)),
                        str(mod.use_even_offset),
                        str(mod.use_quality_normals)
                    ])
                elif mod.type == 'BEVEL':
                    mod_info.extend([
                        str(round(mod.width, 6)),
                        str(mod.segments),
                        str(mod.profile),
                        str(mod.limit_method)
                    ])
                elif mod.type == 'EDGE_SPLIT':
                    mod_info.extend([
                        str(mod.use_edge_angle),
                        str(mod.use_edge_sharp),
                        str(round(mod.split_angle, 4))
                    ])
                elif mod.type == 'DECIMATE':
                    mod_info.extend([
                        str(mod.decimate_type),
                        str(round(mod.ratio, 6)) if hasattr(mod, 'ratio') else '',
                        str(round(mod.angle_limit, 4)) if hasattr(mod, 'angle_limit') else ''
                    ])
                elif mod.type == 'TRIANGULATE':
                    mod_info.extend([
                        str(mod.quad_method),
                        str(mod.ngon_method),
                        str(mod.min_vertices)
                    ])
                elif mod.type == 'ARMATURE':
                    mod_info.extend([
                        str(mod.object.name) if mod.object else 'None',
                        str(mod.use_vertex_groups),
                        str(mod.use_bone_envelopes)
                    ])
                elif mod.type == 'BOOLEAN':
                    mod_info.extend([
                        str(mod.operation),
                        str(mod.object.name) if mod.object else 'None',
                        str(mod.solver)
                    ])
                elif mod.type == 'SCREW':
                    mod_info.extend([
                        str(round(mod.angle, 4)),
                        str(round(mod.screw_offset, 6)),
                        str(mod.iterations),
                        str(mod.axis)
                    ])
                elif mod.type == 'WAVE':
                    mod_info.extend([
                        str(mod.use_x), str(mod.use_y), str(mod.use_z),
                        str(round(mod.height, 6)),
                        str(round(mod.width, 6)),
                        str(round(mod.speed, 6)),
                        str(round(mod.offset, 6))
                    ])
                elif mod.type == 'DISPLACE':
                    mod_info.extend([
                        str(round(mod.strength, 6)),
                        str(mod.direction),
                        str(mod.texture.name) if mod.texture else 'None'
                    ])
                
                # Add common properties that most modifiers have
                try:
                    if hasattr(mod, 'vertex_group') and mod.vertex_group:
                        mod_info.append(f"vgroup:{mod.vertex_group}")
                    if hasattr(mod, 'invert_vertex_group'):
                        mod_info.append(f"invert_vg:{mod.invert_vertex_group}")
                except AttributeError:
                    pass
                
                modifier_data.extend(mod_info)
            
            # Create hash from all modifier data
            modifier_string = ','.join(modifier_data)
            return hashlib.md5(modifier_string.encode()).hexdigest()
            
        except Exception as e:
            # Fallback: basic modifier count and types
            try:
                basic_data = f"{len(obj.modifiers)}_{'_'.join([mod.type for mod in obj.modifiers])}"
                return hashlib.md5(basic_data.encode()).hexdigest()
            except Exception:
                return "unknown_modifiers"
    
    def _calculate_constraints_hash(self, obj):
        """Calculate a hash of object constraints to detect constraint changes"""
        try:
            if not hasattr(obj, 'constraints') or not obj.constraints:
                return "no_constraints"
            
            constraint_data = []
            
            for constraint in obj.constraints:
                constraint_info = [
                    constraint.name,
                    constraint.type,
                    str(constraint.mute),
                    str(constraint.influence)
                ]
                
                # Add type-specific properties for common constraints
                if constraint.type == 'COPY_LOCATION':
                    constraint_info.extend([
                        str(constraint.target.name) if constraint.target else 'None',
                        str(constraint.subtarget),
                        str(constraint.use_x), str(constraint.use_y), str(constraint.use_z),
                        str(constraint.use_offset)
                    ])
                elif constraint.type == 'COPY_ROTATION':
                    constraint_info.extend([
                        str(constraint.target.name) if constraint.target else 'None',
                        str(constraint.subtarget),
                        str(constraint.use_x), str(constraint.use_y), str(constraint.use_z),
                        str(constraint.use_offset)
                    ])
                elif constraint.type == 'COPY_SCALE':
                    constraint_info.extend([
                        str(constraint.target.name) if constraint.target else 'None',
                        str(constraint.subtarget),
                        str(constraint.use_x), str(constraint.use_y), str(constraint.use_z),
                        str(constraint.use_offset)
                    ])
                elif constraint.type == 'TRACK_TO':
                    constraint_info.extend([
                        str(constraint.target.name) if constraint.target else 'None',
                        str(constraint.subtarget),
                        str(constraint.track_axis),
                        str(constraint.up_axis)
                    ])
                elif constraint.type == 'LIMIT_LOCATION':
                    constraint_info.extend([
                        str(constraint.use_min_x), str(constraint.use_max_x),
                        str(constraint.use_min_y), str(constraint.use_max_y),
                        str(constraint.use_min_z), str(constraint.use_max_z),
                        str(round(constraint.min_x, 6)), str(round(constraint.max_x, 6)),
                        str(round(constraint.min_y, 6)), str(round(constraint.max_y, 6)),
                        str(round(constraint.min_z, 6)), str(round(constraint.max_z, 6))
                    ])
                elif constraint.type == 'LIMIT_ROTATION':
                    constraint_info.extend([
                        str(constraint.use_limit_x), str(constraint.use_limit_y), str(constraint.use_limit_z),
                        str(round(constraint.min_x, 4)), str(round(constraint.max_x, 4)),
                        str(round(constraint.min_y, 4)), str(round(constraint.max_y, 4)),
                        str(round(constraint.min_z, 4)), str(round(constraint.max_z, 4))
                    ])
                elif constraint.type == 'CHILD_OF':
                    constraint_info.extend([
                        str(constraint.target.name) if constraint.target else 'None',
                        str(constraint.subtarget)
                    ])
                elif constraint.type == 'FOLLOW_PATH':
                    constraint_info.extend([
                        str(constraint.target.name) if constraint.target else 'None',
                        str(round(constraint.offset_factor, 6)),
                        str(constraint.forward_axis),
                        str(constraint.up_axis)
                    ])
                
                constraint_data.extend(constraint_info)
            
            # Create hash from all constraint data
            constraint_string = ','.join(constraint_data)
            return hashlib.md5(constraint_string.encode()).hexdigest()
            
        except Exception as e:
            # Fallback: basic constraint count and types
            try:
                basic_data = f"{len(obj.constraints)}_{'_'.join([c.type for c in obj.constraints])}"
                return hashlib.md5(basic_data.encode()).hexdigest()
            except Exception:
                return "unknown_constraints"
    
    def _compare_signatures_and_get_deltas(self, current_sig, previous_sig):
        """Compare two data signatures and return changes detected plus specific changed data blocks"""
        changes = {}
        has_changes = False
        changed_data_blocks = set()
        
        # Define data block collections mapping
        data_collections = {
            'objects': bpy.data.objects,
            'meshes': bpy.data.meshes,
            'materials': bpy.data.materials,
            'images': bpy.data.images,
            'texts': bpy.data.texts,
            'actions': bpy.data.actions
        }
        
        for data_type in ["objects", "meshes", "materials", "images", "texts", "actions"]:
            current_items = current_sig.get(data_type, {})
            previous_items = previous_sig.get(data_type, {})
            collection = data_collections[data_type]
            
            # Find additions, removals, and modifications
            added = set(current_items.keys()) - set(previous_items.keys())
            removed = set(previous_items.keys()) - set(current_items.keys())
            common = set(current_items.keys()) & set(previous_items.keys())
            
            # Check for modifications in common items
            modified = set()
            for item_name in common:
                if current_items[item_name] != previous_items[item_name]:
                    modified.add(item_name)
            
            # Add specific changed data blocks to the set
            for item_name in added | modified:
                # Find the actual data block object
                data_block = collection.get(item_name)
                if data_block:
                    changed_data_blocks.add(data_block)
            
            # Note: We don't export removed items since they don't exist anymore
            
            type_changes = len(added) + len(removed) + len(modified)
            if type_changes > 0:
                has_changes = True
                changes[data_type] = {
                    "added": len(added),
                    "removed": len(removed),
                    "modified": len(modified),
                    "total": type_changes
                }
            else:
                changes[data_type] = {
                    "added": 0,
                    "removed": 0,
                    "modified": 0,
                    "total": 0
                }
        
        # Create summary for display
        change_summary = {}
        for data_type, stats in changes.items():
            if stats["total"] > 0:
                change_summary[data_type] = stats["total"]
        
        return has_changes, change_summary, changed_data_blocks
    
    def _get_all_data_blocks(self):
        """Get all data blocks for full export (used in first commit)"""
        data_blocks_to_write = set()
        
        # Data blocks to export as specified in data.instructions.md
        data_collections = {
            'objects': bpy.data.objects,
            'meshes': bpy.data.meshes,
            'materials': bpy.data.materials,
            'images': bpy.data.images,
            'texts': bpy.data.texts,
            'actions': bpy.data.actions
        }
        
        for collection_name, collection in data_collections.items():
            for item in collection:
                data_blocks_to_write.add(item)
        
        return data_blocks_to_write
    
    def _export_delta_data_blocks(self, export_path, changed_data_blocks):
        """Export only the changed data blocks (delta export)"""
        if not changed_data_blocks:
            # If no specific changes, fall back to minimal export
            self._export_data_blocks(export_path)
            return
        
        # Add dependencies for the changed data blocks
        data_blocks_to_write = set(changed_data_blocks)
        
        # Resolve dependencies
        self._add_dependencies(data_blocks_to_write, changed_data_blocks)
        
        # Write only the changed data blocks and their dependencies
        try:
            bpy.data.libraries.write(export_path, data_blocks_to_write, fake_user=True)
        except Exception as e:
            # Fallback to full export if delta export fails
            print(f"Delta export failed: {e}, falling back to full export")
            self._export_data_blocks(export_path)
    
    def _add_dependencies(self, data_blocks_to_write, changed_data_blocks):
        """Add necessary dependencies for changed data blocks"""
        # Keep track of what we've already processed to avoid infinite loops
        processed = set()
        
        def add_block_dependencies(data_block):
            if data_block in processed:
                return
            processed.add(data_block)
            
            # Object dependencies
            if hasattr(data_block, 'data') and data_block.data:
                # Object's mesh/curve/etc data
                data_blocks_to_write.add(data_block.data)
                add_block_dependencies(data_block.data)
            
            # Material dependencies
            if hasattr(data_block, 'materials'):
                for material in data_block.materials:
                    if material:
                        data_blocks_to_write.add(material)
                        add_block_dependencies(material)
            
            if hasattr(data_block, 'material_slots'):
                for slot in data_block.material_slots:
                    if slot.material:
                        data_blocks_to_write.add(slot.material)
                        add_block_dependencies(slot.material)
            
            # Texture/Image dependencies for materials
            if hasattr(data_block, 'node_tree') and data_block.node_tree:
                for node in data_block.node_tree.nodes:
                    if hasattr(node, 'image') and node.image:
                        data_blocks_to_write.add(node.image)
            
            # Animation data dependencies
            if hasattr(data_block, 'animation_data') and data_block.animation_data:
                if data_block.animation_data.action:
                    data_blocks_to_write.add(data_block.animation_data.action)
            
            # Modifier dependencies
            if hasattr(data_block, 'modifiers'):
                for mod in data_block.modifiers:
                    # Boolean modifier object dependency
                    if mod.type == 'BOOLEAN' and hasattr(mod, 'object') and mod.object:
                        data_blocks_to_write.add(mod.object)
                        add_block_dependencies(mod.object)
                    
                    # Array modifier object dependencies
                    elif mod.type == 'ARRAY':
                        if hasattr(mod, 'offset_object') and mod.offset_object:
                            data_blocks_to_write.add(mod.offset_object)
                        if hasattr(mod, 'start_cap') and mod.start_cap:
                            data_blocks_to_write.add(mod.start_cap)
                        if hasattr(mod, 'end_cap') and mod.end_cap:
                            data_blocks_to_write.add(mod.end_cap)
                    
                    # Mirror modifier object dependency
                    elif mod.type == 'MIRROR' and hasattr(mod, 'mirror_object') and mod.mirror_object:
                        data_blocks_to_write.add(mod.mirror_object)
                    
                    # Armature modifier dependency
                    elif mod.type == 'ARMATURE' and hasattr(mod, 'object') and mod.object:
                        data_blocks_to_write.add(mod.object)
                        # Also include the armature data
                        if mod.object.data:
                            data_blocks_to_write.add(mod.object.data)
                    
                    # Curve modifier dependency
                    elif mod.type == 'CURVE' and hasattr(mod, 'object') and mod.object:
                        data_blocks_to_write.add(mod.object)
                        if mod.object.data:
                            data_blocks_to_write.add(mod.object.data)
                    
                    # Displace modifier texture dependency
                    elif mod.type == 'DISPLACE' and hasattr(mod, 'texture') and mod.texture:
                        data_blocks_to_write.add(mod.texture)
                        # If texture uses an image, include that too
                        if hasattr(mod.texture, 'image') and mod.texture.image:
                            data_blocks_to_write.add(mod.texture.image)
            
            # Constraint dependencies
            if hasattr(data_block, 'constraints'):
                for constraint in data_block.constraints:
                    # Add constraint target objects as dependencies
                    if hasattr(constraint, 'target') and constraint.target:
                        data_blocks_to_write.add(constraint.target)
                        add_block_dependencies(constraint.target)
        
        # Add dependencies for all changed blocks
        for data_block in list(changed_data_blocks):
            add_block_dependencies(data_block)
    
    def _get_data_block_counts(self):
        """Get counts of current data blocks"""
        return {
            "objects": len(bpy.data.objects),
            "meshes": len(bpy.data.meshes),
            "materials": len(bpy.data.materials),
            "images": len(bpy.data.images),
            "texts": len(bpy.data.texts),
            "actions": len(bpy.data.actions)
        }
    
    def _get_previous_data_block_counts(self, previous_blend_path):
        """Get counts of data blocks from previous commit by temporarily loading it"""
        # This is a simplified approach - in practice, you might want to store
        # data block metadata in the commit information for better performance
        try:
            # For now, we'll estimate based on file size differences
            # A more sophisticated approach would involve loading the previous blend file
            # and analyzing its contents, but that's complex and slow
            
            # Return current counts as fallback (this ensures changes are detected)
            return self._get_data_block_counts()
            
        except Exception:
            # If we can't analyze previous commit, assume everything is new
            return {}
    
    def _generate_commit_hash(self, timestamp, message, parent_hash):
        """Generate SHA-256 hash for commit"""
        content = f"{timestamp}_{message}_{parent_hash or ''}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _export_data_blocks(self, export_path):
        """Export specified data blocks using bpy.data.libraries.write"""
        # Data blocks to export as specified in data.instructions.md
        data_blocks = {
            'objects': bpy.data.objects,
            'meshes': bpy.data.meshes,
            'materials': bpy.data.materials,
            'images': bpy.data.images,
            'texts': bpy.data.texts,
            'actions': bpy.data.actions
        }
        
        # Collect all data blocks to write
        data_blocks_to_write = set()
        
        for block_type, collection in data_blocks.items():
            for item in collection:
                data_blocks_to_write.add(item)
        
        # Write to .blend file
        bpy.data.libraries.write(export_path, data_blocks_to_write, fake_user=True)


def register_commit():
    bpy.utils.register_class(GITBLEND_OT_Commit)


def unregister_commit():
    bpy.utils.unregister_class(GITBLEND_OT_Commit)

