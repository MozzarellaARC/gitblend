import bpy
import os
import json
import hashlib
import time
from datetime import datetime
from pathlib import Path


class GITBLEND_OT_RefreshHistory(bpy.types.Operator):
    bl_idname = "gitblend.refresh_history"
    bl_label = "Refresh History"
    bl_description = "Refresh the commit history"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        populate_commit_history(context)
        self.report({'INFO'}, "Commit history refreshed")
        return {'FINISHED'}


class GITBLEND_OT_RefreshStatus(bpy.types.Operator):
    bl_idname = "gitblend.refresh_status"
    bl_label = "Refresh Status"
    bl_description = "Refresh the initialization status"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        check_and_update_initialized_property(context)
        return {'FINISHED'}


class GITBLEND_OT_Initialize(bpy.types.Operator):
    bl_idname = "gitblend.initialize"
    bl_label = "Initialize Git Blend"
    bl_description = "Initialize git blend repository for this .blend file"
    bl_options = {'REGISTER', 'UNDO'}
    
    commit_message: bpy.props.StringProperty(
        name="Initial Commit Message",
        description="Message for the initial commit",
        default="Initial commit"
    )
    
    @classmethod
    def poll(cls, context):
        # Can only initialize if blend file is saved
        return bpy.data.filepath != ""
    
    def execute(self, context):
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        gitblend_dir = project_dir / ".gitblend"
        
        # Check if .gitblend already exists
        if gitblend_dir.exists():
            self.report({'INFO'}, "Git Blend already initialized")
            return {'CANCELLED'}
        
        try:
            # Create .gitblend directory
            gitblend_dir.mkdir()
            
            # Generate commit hash using current timestamp and content
            timestamp = datetime.now().isoformat()
            current_time = int(time.time())
            
            # Create initial commit metadata
            commit_data = {
                "hash": self._generate_commit_hash(current_time, self.commit_message),
                "timestamp": timestamp,
                "message": self.commit_message,
                "parent": None,  # Initial commit has no parent
                "delta_export": False,  # Initial commit is always full export
                "changed_blocks": []  # No previous state to compare
            }
            
            # Save initial metadata
            metadata_file = gitblend_dir / "commits.json"
            metadata = {
                "version": 1,
                "commits": [commit_data]
            }
            
            with metadata_file.open('w') as f:
                json.dump(metadata, f, indent=2)
            
            # Export data blocks to .blend file
            blend_filename = f"{commit_data['hash']}.blend"
            blend_export_path = gitblend_dir / blend_filename
            
            self._export_data_blocks(str(blend_export_path))
            
            # Create initial signature file for change detection
            signature_file = gitblend_dir / f"{commit_data['hash']}_signature.json"
            initial_signature = self._generate_initial_signature()
            with signature_file.open('w') as f:
                json.dump(initial_signature, f, indent=2)
            
            # Update initialized property
            context.scene.gitblend_props.initialized = True
            
            # Populate commit history
            populate_commit_history(context)
            
            self.report({'INFO'}, f"Git Blend initialized with commit: {commit_data['hash'][:8]}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to initialize: {str(e)}")
            return {'CANCELLED'}
    
    def _generate_commit_hash(self, timestamp, message):
        """Generate SHA-256 hash for commit"""
        content = f"{timestamp}_{message}"
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
    
    def _generate_initial_signature(self):
        """Generate signature for initial commit (same as commit signature)"""
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
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


def register_initialize():
    bpy.utils.register_class(GITBLEND_OT_RefreshHistory)
    bpy.utils.register_class(GITBLEND_OT_RefreshStatus)
    bpy.utils.register_class(GITBLEND_OT_Initialize)
    # Add handlers to check initialization status
    bpy.app.handlers.load_post.append(on_file_load_check_initialization)
    bpy.app.handlers.save_post.append(on_file_save_check_initialization)


def unregister_initialize():
    # Remove handlers
    if on_file_load_check_initialization in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_file_load_check_initialization)
    if on_file_save_check_initialization in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(on_file_save_check_initialization)
    bpy.utils.unregister_class(GITBLEND_OT_Initialize)
    bpy.utils.unregister_class(GITBLEND_OT_RefreshStatus)
    bpy.utils.unregister_class(GITBLEND_OT_RefreshHistory)


@bpy.app.handlers.persistent
def on_file_load_check_initialization(dummy):
    """Handler to check initialization status when a blend file is loaded"""
    try:
        context = bpy.context
        check_and_update_initialized_property(context)
        # Also populate commit history if initialized
        if context.scene.gitblend_props.initialized:
            populate_commit_history(context)
    except Exception:
        pass  # Silently fail if context is not available


@bpy.app.handlers.persistent
def on_file_save_check_initialization(dummy):
    """Handler to check initialization status when a blend file is saved"""
    try:
        context = bpy.context
        check_and_update_initialized_property(context)
        # Also populate commit history if initialized
        if context.scene.gitblend_props.initialized:
            populate_commit_history(context)
    except Exception:
        pass  # Silently fail if context is not available


# Utility functions for other modules
def is_gitblend_initialized(project_dir):
    """Check if .gitblend directory exists"""
    return (project_dir / ".gitblend").exists()


def check_and_update_initialized_property(context):
    """Check if gitblend is initialized and update the property accordingly"""
    if not bpy.data.filepath:
        context.scene.gitblend_props.initialized = False
        return False
    
    try:
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        is_initialized = is_gitblend_initialized(project_dir)
        context.scene.gitblend_props.initialized = is_initialized
        return is_initialized
    except Exception:
        context.scene.gitblend_props.initialized = False
        return False


def check_initialized_status(context):
    """Read-only check of initialization status - safe to call from panel draw"""
    if not bpy.data.filepath:
        return False
    
    try:
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        return is_gitblend_initialized(project_dir)
    except Exception:
        return False


def populate_commit_history(context):
    """Load commit history from metadata file into UI properties"""
    if not bpy.data.filepath:
        # Clear history if no file is open
        context.scene.gitblend_props.commits.clear()
        return
    
    blend_path = Path(bpy.data.filepath).resolve()
    project_dir = blend_path.parent
    metadata_file = project_dir / ".gitblend" / "commits.json"
    
    props = context.scene.gitblend_props
    props.commits.clear()
    
    if not metadata_file.exists():
        return
    
    try:
        with metadata_file.open('r') as f:
            metadata = json.load(f)
        
        # Load commits in reverse order (newest first)
        commits_data = metadata.get('commits', [])
        for commit_data in reversed(commits_data):
            commit_entry = props.commits.add()
            commit_entry.hash = commit_data.get('hash', '')
            commit_entry.message = commit_data.get('message', '')
            commit_entry.timestamp = commit_data.get('timestamp', '')
            
    except Exception as e:
        print(f"Failed to load commit history: {e}")


def populate_ui_from_metadata(context):
    """Load commit history from metadata file into UI (legacy function)"""
    populate_commit_history(context)


def has_branches_from_commit(project_dir, commit_hash):
    """Check if commit has branches (placeholder for future implementation)"""
    return False


def update_branch_status(context):
    """Update branch status in UI (placeholder for future implementation)"""
    props = context.scene.gitblend_props
    props.current_branch_display = "main"
    props.is_on_head = True


def get_branch_names(project_dir):
    """Get list of branch names (placeholder for future implementation)"""
    return ["main"]


def populate_branch_commits(context):
    """Populate branch-specific commits (placeholder for future implementation)"""
    props = context.scene.gitblend_props
    # For now, just copy all commits to branch_commits
    props.branch_commits.clear()
    for commit in props.commits:
        branch_commit = props.branch_commits.add()
        branch_commit.hash = commit.hash
        branch_commit.message = commit.message
        branch_commit.timestamp = commit.timestamp


def should_show_commit_button_on_detached(context):
    """Check if commit button should be shown when detached (placeholder)"""
    return False