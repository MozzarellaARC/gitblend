import hashlib
from typing import Dict, List, Optional, Tuple, Any
import bpy # type: ignore # type: ignore


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _fmt_floats(vals, digits: int = 6) -> str:
    return ",".join(f"{float(v):.{digits}f}" for v in vals)


def _matrix_hash(m) -> str:
    vals = []
    try:
        for i in range(4):
            for j in range(4):
                vals.append(m[i][j])
    except Exception:
        pass
    return _sha256(_fmt_floats(vals))


def _list_hash(values: List[str]) -> str:
    return _sha256("|".join(values))


# ============= Helper Functions for Property Extraction =============

def _get_custom_properties(obj: Any) -> str:
    """Extract custom properties (ID properties) as a hash."""
    try:
        props = []
        for key in obj.keys():
            if not key.startswith("_"):  # Skip internal props
                val = obj[key]
                # Handle different value types
                if isinstance(val, (int, float, bool, str)):
                    props.append(f"{key}:{val}")
                elif hasattr(val, "__len__"):  # Arrays/sequences
                    props.append(f"{key}:[{','.join(str(v) for v in val)}]")
                else:
                    props.append(f"{key}:{str(val)}")
        return _sha256("|".join(sorted(props)))
    except Exception:
        return ""


def _get_visibility_flags(obj: bpy.types.Object) -> str:
    """Extract visibility and render flags."""
    try:
        flags = []
        # Visibility settings
        flags.append(f"hide_viewport:{int(obj.hide_viewport)}")
        flags.append(f"hide_render:{int(obj.hide_render)}")
        flags.append(f"hide_select:{int(obj.hide_select)}")
        flags.append(f"visible_camera:{int(obj.visible_camera)}")
        flags.append(f"visible_diffuse:{int(obj.visible_diffuse)}")
        flags.append(f"visible_glossy:{int(obj.visible_glossy)}")
        flags.append(f"visible_transmission:{int(obj.visible_transmission)}")
        flags.append(f"visible_volume_scatter:{int(obj.visible_volume_scatter)}")
        flags.append(f"visible_shadow:{int(obj.visible_shadow)}")
        # Display settings
        flags.append(f"show_name:{int(obj.show_name)}")
        flags.append(f"show_axis:{int(obj.show_axis)}")
        flags.append(f"show_in_front:{int(obj.show_in_front)}")
        flags.append(f"show_bounds:{int(obj.show_bounds)}")
        if hasattr(obj, "display_bounds_type"):
            flags.append(f"bounds_type:{obj.display_bounds_type}")
        return _sha256("|".join(flags))
    except Exception:
        return ""


def _get_constraints_hash(constraints) -> str:
    """Extract constraints data as hash."""
    try:
        parts = []
        for c in constraints:
            con_data = [
                str(c.type),
                c.name,
                f"{c.influence:.6f}",
                f"mute:{int(c.mute)}",
            ]
            # Target info
            if hasattr(c, "target"):
                con_data.append(f"target:{c.target.name if c.target else ''}")
            if hasattr(c, "subtarget"):
                con_data.append(f"subtarget:{c.subtarget}")
            # Space settings
            if hasattr(c, "owner_space"):
                con_data.append(f"owner_space:{c.owner_space}")
            if hasattr(c, "target_space"):
                con_data.append(f"target_space:{c.target_space}")
            parts.append("|".join(con_data))
        return _sha256("||".join(parts))
    except Exception:
        return ""


def _get_modifiers_hash(obj: bpy.types.Object) -> str:
    """Extract detailed modifier data including all settings."""
    try:
        parts = []
        for m in obj.modifiers:
            mod_data = [f"type:{m.type}", f"name:{m.name}"]
            # Common modifier properties
            if hasattr(m, "show_viewport"):
                mod_data.append(f"show_viewport:{int(m.show_viewport)}")
            if hasattr(m, "show_render"):
                mod_data.append(f"show_render:{int(m.show_render)}")
            
            # Type-specific properties
            if m.type == "SUBSURF":
                mod_data.extend([
                    f"levels:{m.levels}",
                    f"render_levels:{m.render_levels}",
                    f"quality:{m.quality}",
                    f"uv_smooth:{m.uv_smooth}",
                    f"boundary_smooth:{m.boundary_smooth}",
                    f"use_creases:{int(m.use_creases)}",
                ])
            elif m.type == "ARRAY":
                mod_data.extend([
                    f"count:{m.count}",
                    f"fit_type:{m.fit_type}",
                    f"use_relative_offset:{int(m.use_relative_offset)}",
                    f"use_constant_offset:{int(m.use_constant_offset)}",
                ])
                if m.use_relative_offset:
                    mod_data.append(f"relative_offset:{_fmt_floats(m.relative_offset_displace)}")
                if m.use_constant_offset:
                    mod_data.append(f"constant_offset:{_fmt_floats(m.constant_offset_displace)}")
            elif m.type == "MIRROR":
                mod_data.extend([
                    f"use_axis:{int(m.use_axis[0])},{int(m.use_axis[1])},{int(m.use_axis[2])}",
                    f"use_bisect_axis:{int(m.use_bisect_axis[0])},{int(m.use_bisect_axis[1])},{int(m.use_bisect_axis[2])}",
                    f"use_bisect_flip_axis:{int(m.use_bisect_flip_axis[0])},{int(m.use_bisect_flip_axis[1])},{int(m.use_bisect_flip_axis[2])}",
                    f"mirror_object:{m.mirror_object.name if m.mirror_object else ''}",
                ])
            elif m.type == "SOLIDIFY":
                mod_data.extend([
                    f"thickness:{m.thickness:.6f}",
                    f"offset:{m.offset:.6f}",
                    f"use_even_offset:{int(m.use_even_offset)}",
                    f"use_quality_normals:{int(m.use_quality_normals)}",
                ])
            elif m.type == "BEVEL":
                mod_data.extend([
                    f"width:{m.width:.6f}",
                    f"segments:{m.segments}",
                    f"limit_method:{m.limit_method}",
                    f"angle_limit:{m.angle_limit:.6f}",
                ])
            elif m.type == "ARMATURE":
                mod_data.extend([
                    f"object:{m.object.name if m.object else ''}",
                    f"use_deform_preserve_volume:{int(m.use_deform_preserve_volume)}",
                    f"use_vertex_groups:{int(m.use_vertex_groups)}",
                ])
            elif m.type == "NODES":
                # Geometry nodes modifier
                mod_data.append(f"node_group:{m.node_group.name if m.node_group else ''}")
                if m.node_group:
                    mod_data.append(_get_geometry_nodes_hash(m.node_group))
            # Add more modifier types as needed
            
            parts.append("|".join(mod_data))
        return _sha256("||".join(parts))
    except Exception:
        return ""


def _get_geometry_nodes_hash(node_group: bpy.types.NodeTree) -> str:
    """Hash geometry nodes setup including node graph structure."""
    try:
        parts = []
        # Node tree metadata
        parts.append(f"name:{node_group.name}")
        
        # Nodes
        for node in node_group.nodes:
            node_data = [
                f"node:{node.name}",
                f"type:{node.type}",
                f"location:{_fmt_floats(node.location)}",
            ]
            # Node-specific properties
            if hasattr(node, "operation"):
                node_data.append(f"operation:{node.operation}")
            if hasattr(node, "data_type"):
                node_data.append(f"data_type:{node.data_type}")
            # Input values
            for input in node.inputs:
                if hasattr(input, "default_value"):
                    try:
                        val = input.default_value
                        if hasattr(val, "__len__"):
                            node_data.append(f"input:{input.name}={_fmt_floats(val)}")
                        else:
                            node_data.append(f"input:{input.name}={val}")
                    except:
                        pass
            parts.append("|".join(node_data))
        
        # Links
        for link in node_group.links:
            parts.append(f"link:{link.from_node.name}.{link.from_socket.name}->{link.to_node.name}.{link.to_socket.name}")
        
        return f"geo_nodes:{_sha256('||'.join(parts))}"
    except Exception:
        return "geo_nodes:"


def _get_particle_systems_hash(obj: bpy.types.Object) -> str:
    """Extract particle system settings."""
    try:
        parts = []
        for ps in obj.particle_systems:
            ps_data = [
                f"name:{ps.name}",
                f"seed:{ps.seed}",
            ]
            settings = ps.settings
            if settings:
                ps_data.extend([
                    f"type:{settings.type}",
                    f"count:{settings.count}",
                    f"frame_start:{settings.frame_start}",
                    f"frame_end:{settings.frame_end}",
                    f"lifetime:{settings.lifetime}",
                    f"emit_from:{settings.emit_from}",
                    f"physics_type:{settings.physics_type}",
                    f"render_type:{settings.render_type}",
                ])
                # Emission
                if hasattr(settings, "use_emit_random"):
                    ps_data.append(f"use_emit_random:{int(settings.use_emit_random)}")
                # Physics
                if settings.physics_type != 'NO':
                    ps_data.extend([
                        f"mass:{settings.mass:.6f}",
                        f"damping:{settings.damping:.6f}",
                        f"size:{settings.particle_size:.6f}",
                    ])
            parts.append("|".join(ps_data))
        return _sha256("||".join(parts))
    except Exception:
        return ""


def _get_drivers_hash(obj) -> str:
    """Extract animation drivers data."""
    try:
        parts = []
        if obj.animation_data and obj.animation_data.drivers:
            for fcurve in obj.animation_data.drivers:
                driver = fcurve.driver
                drv_data = [
                    f"path:{fcurve.data_path}",
                    f"index:{fcurve.array_index}",
                    f"type:{driver.type}",
                    f"expr:{driver.expression}",
                ]
                # Variables
                for var in driver.variables:
                    drv_data.append(f"var:{var.name}={var.type}")
                    for target in var.targets:
                        drv_data.append(f"target:{target.id_type}:{target.data_path}")
                parts.append("|".join(drv_data))
        return _sha256("||".join(parts))
    except Exception:
        return ""


def _get_material_meta_hash(material: bpy.types.Material) -> str:
    """Extract material metadata including node setup."""
    try:
        parts = []
        parts.append(f"name:{material.name}")
        parts.append(f"use_nodes:{int(material.use_nodes)}")
        
        if material.use_nodes and material.node_tree:
            # Node tree structure
            for node in material.node_tree.nodes:
                node_data = [
                    f"node:{node.name}",
                    f"type:{node.type}",
                ]
                # Shader node specifics
                if node.type == 'BSDF_PRINCIPLED':
                    for input in node.inputs:
                        if hasattr(input, "default_value"):
                            try:
                                val = input.default_value
                                if hasattr(val, "__len__"):
                                    node_data.append(f"{input.name}:{_fmt_floats(val)}")
                                else:
                                    node_data.append(f"{input.name}:{val}")
                            except:
                                pass
                parts.append("|".join(node_data))
            
            # Links
            for link in material.node_tree.links:
                parts.append(f"link:{link.from_node.name}.{link.from_socket.name}->{link.to_node.name}.{link.to_socket.name}")
        else:
            # Non-node material properties
            parts.append(f"diffuse:{_fmt_floats(material.diffuse_color)}")
            parts.append(f"specular:{material.specular_intensity:.6f}")
            parts.append(f"roughness:{material.roughness:.6f}")
            parts.append(f"metallic:{material.metallic:.6f}")
        
        return _sha256("||".join(parts))
    except Exception:
        return ""


def _get_uv_color_attributes_hash(mesh: bpy.types.Mesh) -> str:
    """Extract UV and color attribute data."""
    try:
        parts = []
        
        # UV layers with actual data
        for uv_layer in mesh.uv_layers:
            uv_data = [f"uv_layer:{uv_layer.name}"]
            # Sample some UV coordinates for change detection
            sample_uvs = []
            for i, uv in enumerate(uv_layer.data[:100]):  # Sample first 100
                sample_uvs.append(_fmt_floats(uv.uv))
            uv_data.append(f"uvs:{_sha256('|'.join(sample_uvs))}")
            parts.append("|".join(uv_data))
        
        # Color attributes (Blender 4.2)
        if hasattr(mesh, "color_attributes"):
            for color_attr in mesh.color_attributes:
                color_data = [
                    f"color_attr:{color_attr.name}",
                    f"domain:{color_attr.domain}",
                    f"data_type:{color_attr.data_type}",
                ]
                parts.append("|".join(color_data))
        
        # Vertex colors (older Blender versions)
        elif hasattr(mesh, "vertex_colors"):
            for vc in mesh.vertex_colors:
                vc_data = [f"vertex_color:{vc.name}"]
                # Sample some colors
                sample_colors = []
                for i, col in enumerate(vc.data[:100]):  # Sample first 100
                    sample_colors.append(_fmt_floats(col.color))
                vc_data.append(f"colors:{_sha256('|'.join(sample_colors))}")
                parts.append("|".join(vc_data))
        
        return _sha256("||".join(parts))
    except Exception:
        return ""


def _get_shapekeys_detailed_hash(mesh: bpy.types.Mesh) -> str:
    """Extract detailed shapekey data including vertex positions."""
    try:
        parts = []
        kb = getattr(getattr(mesh, "shape_keys", None), "key_blocks", None)
        if kb:
            for key in kb:
                key_data = [
                    f"name:{key.name}",
                    f"value:{key.value:.6f}",
                    f"min:{key.slider_min:.6f}",
                    f"max:{key.slider_max:.6f}",
                    f"mute:{int(key.mute)}",
                ]
                # Sample vertex positions from shapekey
                sample_verts = []
                for i, point in enumerate(key.data[:50]):  # Sample first 50 verts
                    sample_verts.append(_fmt_floats(point.co))
                key_data.append(f"verts:{_sha256('|'.join(sample_verts))}")
                parts.append("|".join(key_data))
        return _sha256("||".join(parts))
    except Exception:
        return ""


# ============= Main Signature Computation =============

def compute_object_signature(obj: bpy.types.Object) -> Dict:
    # L2-ish signature: names/meta + transforms + dims + counts
    sig: Dict = {}
    sig["name"] = obj.name or ""
    sig["parent"] = obj.parent.name if obj.parent else ""
    sig["type"] = obj.type
    # Data block name (helps distinguish reused data)
    try:
        sig["data_name"] = getattr(obj, "data", None).name if getattr(obj, "data", None) else ""
    except Exception:
        sig["data_name"] = ""
    
    # Transforms and dimensions
    sig["transform"] = _matrix_hash(obj.matrix_world)
    try:
        sig["dims"] = _sha256(_fmt_floats(obj.dimensions))
    except Exception:
        sig["dims"] = ""
    
    # Common properties for all objects
    sig["visibility_flags"] = _get_visibility_flags(obj)
    sig["custom_properties"] = _get_custom_properties(obj)
    sig["constraints"] = _get_constraints_hash(obj.constraints)
    sig["drivers"] = _get_drivers_hash(obj)
    
    # Instance properties
    if obj.type == 'EMPTY' or obj.instance_type != 'NONE':
        sig["instance_type"] = obj.instance_type
        sig["instance_collection"] = obj.instance_collection.name if obj.instance_collection else ""
        sig["use_instance_vertices_rotation"] = int(obj.use_instance_vertices_rotation)
        sig["use_instance_faces_scale"] = int(obj.use_instance_faces_scale)
        sig["show_instancer_for_viewport"] = int(obj.show_instancer_for_viewport)
        sig["show_instancer_for_render"] = int(obj.show_instancer_for_render)
    
    # Materials (all objects that have material_slots)
    try:
        mats = []
        for slot in getattr(obj, "material_slots", []):
            if slot.material:
                mats.append(slot.material.name)
                # Add material meta hash
                mats.append(_get_material_meta_hash(slot.material))
            else:
                mats.append("")
    except Exception:
        mats = []
    sig["materials"] = _list_hash(mats)
    
    # Particle systems
    sig["particle_systems"] = _get_particle_systems_hash(obj)

    obj_type = getattr(obj, "type", None)
    has_data = getattr(obj, "data", None) is not None

    if obj_type == "MESH" and has_data:
        me = obj.data
        sig["verts"] = int(len(me.vertices))
        # Topology counts
        try:
            sig["edges"] = int(len(me.edges))
        except Exception:
            sig["edges"] = 0
        try:
            sig["polygons"] = int(len(me.polygons))
        except Exception:
            sig["polygons"] = 0
        
        # Enhanced modifiers hash
        sig["modifiers"] = _get_modifiers_hash(obj)
        
        # Vertex group names
        vgn = [vg.name for vg in getattr(obj, "vertex_groups", [])]
        sig["vgroups"] = _list_hash(sorted(vgn))
        
        # UV and color attributes
        sig["uv_color_data"] = _get_uv_color_attributes_hash(me)
        
        # UV layers names (meta)
        uvl = getattr(me, "uv_layers", None)
        uvs = [uv.name for uv in uvl] if uvl else []
        sig["uv_meta"] = _list_hash(uvs)
        
        # Detailed shapekeys
        sig["shapekeys_detailed"] = _get_shapekeys_detailed_hash(me)
        
        # Shapekeys names (order)
        kb = getattr(getattr(me, "shape_keys", None), "key_blocks", None)
        sk = [k.name for k in kb] if kb else []
        sig["shapekeys_meta"] = _list_hash(sk)
        
        # Shapekey values snapshot (name:value)
        try:
            if kb:
                vals = [f"{k.name}:{float(getattr(k, 'value', 0.0)):.6f}" for k in kb]
            else:
                vals = []
        except Exception:
            vals = []
        sig["shapekeys_values"] = _list_hash(vals)
        
        # Geometry hash (object-space vertex coordinates)
        try:
            coords = []
            for v in me.vertices:
                co = v.co
                coords.extend((f"{float(co.x):.6f}", f"{float(co.y):.6f}", f"{float(co.z):.6f}"))
            sig["geo_hash"] = _sha256("|".join(coords))
        except Exception:
            sig["geo_hash"] = ""
            
    elif obj_type == "LATTICE" and has_data:
        lat = obj.data
        sig["lattice_meta"] = _sha256("|".join([
            f"points_u:{lat.points_u}",
            f"points_v:{lat.points_v}",
            f"points_w:{lat.points_w}",
            f"interpolation_type_u:{lat.interpolation_type_u}",
            f"interpolation_type_v:{lat.interpolation_type_v}",
            f"interpolation_type_w:{lat.interpolation_type_w}",
        ]))
        # Lattice point positions
        try:
            coords = []
            for point in lat.points:
                co = point.co_deform
                coords.append(_fmt_floats([co.x, co.y, co.z]))
            sig["lattice_points"] = _sha256("|".join(coords))
        except:
            sig["lattice_points"] = ""
        sig["modifiers"] = _get_modifiers_hash(obj)
        
    elif obj_type == "SURFACE" and has_data:
        # NURBS surface (similar to curve but 2D parametric)
        surf = obj.data
        sig["surface_meta"] = _sha256("|".join([
            f"resolution_u:{surf.resolution_u}",
            f"resolution_v:{surf.resolution_v}",
            f"render_resolution_u:{surf.render_resolution_u}",
            f"render_resolution_v:{surf.render_resolution_v}",
        ]))
        # Control points
        try:
            parts = []
            for spline in surf.splines:
                for point in spline.points:
                    co = point.co
                    parts.append(_fmt_floats([co.x, co.y, co.z, co.w]))
            sig["surface_points"] = _sha256("|".join(parts))
        except:
            sig["surface_points"] = ""
        sig["modifiers"] = _get_modifiers_hash(obj)
        
    elif obj_type == "META" and has_data:
        # Metaball
        mb = obj.data
        sig["meta_meta"] = _sha256("|".join([
            f"resolution:{mb.resolution:.6f}",
            f"render_resolution:{mb.render_resolution:.6f}",
            f"threshold:{mb.threshold:.6f}",
        ]))
        # Metaball elements
        try:
            parts = []
            for elem in mb.elements:
                parts.extend([
                    f"type:{elem.type}",
                    f"co:{_fmt_floats(elem.co)}",
                    f"radius:{elem.radius:.6f}",
                    f"stiffness:{elem.stiffness:.6f}",
                ])
                if elem.type in ('ELLIPSOID', 'CAPSULE'):
                    parts.append(f"size:{_fmt_floats([elem.size_x, elem.size_y, elem.size_z])}")
                if elem.type == 'PLANE':
                    parts.append(f"size:{_fmt_floats([elem.size_x, elem.size_y])}")
            sig["meta_elements"] = _sha256("|".join(parts))
        except:
            sig["meta_elements"] = ""
            
    elif obj_type == "FONT" and has_data:
        # Text/Font object
        txt = obj.data
        sig["font_meta"] = _sha256("|".join([
            f"body:{txt.body}",
            f"align_x:{txt.align_x}",
            f"align_y:{txt.align_y}",
            f"size:{txt.size:.6f}",
            f"shear:{txt.shear:.6f}",
            f"offset_x:{txt.offset_x:.6f}",
            f"offset_y:{txt.offset_y:.6f}",
            f"extrude:{txt.extrude:.6f}",
            f"bevel_depth:{txt.bevel_depth:.6f}",
            f"bevel_resolution:{txt.bevel_resolution}",
            f"font:{txt.font.name if txt.font else ''}",
        ]))
        sig["modifiers"] = _get_modifiers_hash(obj)
        
    elif obj_type == "VOLUME" and has_data:
        # Volume object (OpenVDB)
        vol = obj.data
        sig["volume_meta"] = _sha256("|".join([
            f"filepath:{vol.filepath}",
            f"is_sequence:{int(vol.is_sequence)}",
            f"frame_start:{vol.frame_start}",
            f"frame_duration:{vol.frame_duration}",
            f"frame_offset:{vol.frame_offset}",
            f"sequence_mode:{vol.sequence_mode}",
        ]))
        # Grid metadata
        try:
            grids = []
            for grid in vol.grids:
                grids.append(f"{grid.name}:{grid.data_type}")
            sig["volume_grids"] = _sha256("|".join(grids))
        except:
            sig["volume_grids"] = ""
        sig["modifiers"] = _get_modifiers_hash(obj)
        
    elif obj_type == "POINTCLOUD" and has_data:
        # Point Cloud (geometry nodes)
        pc = obj.data
        try:
            sig["pointcloud_count"] = len(pc.points)
            # Attributes
            attrs = []
            for attr in pc.attributes:
                attrs.append(f"{attr.name}:{attr.data_type}:{attr.domain}")
            sig["pointcloud_attributes"] = _sha256("|".join(attrs))
        except:
            sig["pointcloud_count"] = 0
            sig["pointcloud_attributes"] = ""
        sig["modifiers"] = _get_modifiers_hash(obj)
        
    elif obj_type == "GPENCIL" and has_data:
        # Grease Pencil
        gp = obj.data
        sig["gpencil_meta"] = _sha256("|".join([
            f"pixel_factor:{gp.pixel_factor:.6f}",
            f"use_stroke_edit_mode:{int(gp.use_stroke_edit_mode)}",
        ]))
        # Layers and frames
        try:
            parts = []
            for layer in gp.layers:
                parts.append(f"layer:{layer.info}")
                parts.append(f"opacity:{layer.opacity:.6f}")
                parts.append(f"use_lights:{int(layer.use_lights)}")
                # Frames
                for frame in layer.frames:
                    parts.append(f"frame:{frame.frame_number}")
                    # Strokes
                    for stroke in frame.strokes:
                        parts.append(f"points:{len(stroke.points)}")
                        parts.append(f"material:{stroke.material_index}")
                        parts.append(f"line_width:{stroke.line_width}")
            sig["gpencil_data"] = _sha256("|".join(parts))
        except:
            sig["gpencil_data"] = ""
        sig["modifiers"] = _get_modifiers_hash(obj)
        
    elif obj_type == "LIGHT" and has_data:
        # Light-specific meta
        li = obj.data  # bpy.types.Light
        vals = []
        try:
            vals.append(str(getattr(li, "type", "")))
            col = getattr(li, "color", None)
            if col is not None:
                vals.append(_fmt_floats(col))
            vals.append(f"{float(getattr(li, 'energy', 0.0)):.6f}")
            # Common shadow/soft size
            if hasattr(li, "shadow_soft_size"):
                vals.append(f"{float(getattr(li, 'shadow_soft_size', 0.0)):.6f}")
            # Sun angle or Spot specifics
            if hasattr(li, "angle"):
                vals.append(f"{float(getattr(li, 'angle', 0.0)):.6f}")
            if getattr(li, "type", "") == "SPOT":
                vals.append(f"{float(getattr(li, 'spot_size', 0.0)):.6f}")
                vals.append(f"{float(getattr(li, 'spot_blend', 0.0)):.6f}")
            if getattr(li, "type", "") == "AREA":
                vals.append(str(getattr(li, "shape", "")))
                vals.append(f"{float(getattr(li, 'size', 0.0)):.6f}")
                if hasattr(li, "size_y"):
                    vals.append(f"{float(getattr(li, 'size_y', 0.0)):.6f}")
        except Exception:
            pass
        sig["light_meta"] = _sha256("|".join(vals))
        
    elif obj_type == "CAMERA" and has_data:
        # Camera-specific meta
        cam = obj.data  # bpy.types.Camera
        vals = []
        try:
            vals.append(str(getattr(cam, "type", "")))
            # Core intrinsics
            for attr in ("lens", "ortho_scale", "sensor_width", "sensor_height",
                         "shift_x", "shift_y", "clip_start", "clip_end"):
                if hasattr(cam, attr):
                    vals.append(f"{float(getattr(cam, attr)):.6f}")
            # Depth of Field
            dof = getattr(cam, "dof", None)
            if dof is not None:
                use_dof = bool(getattr(dof, "use_dof", False))
                vals.append("DOF:1" if use_dof else "DOF:0")
                for attr in ("focus_distance", "aperture_fstop", "aperture_size"):
                    if hasattr(dof, attr):
                        try:
                            vals.append(f"{float(getattr(dof, attr)):.6f}")
                        except Exception:
                            pass
        except Exception:
            pass
        sig["camera_meta"] = _sha256("|".join(vals))
        
    elif obj_type == "ARMATURE" and has_data:
        arm = obj.data  # bpy.types.Armature
        # Rest armature metadata
        vals = []
        try:
            vals.append(str(getattr(arm, "display_type", "")))
            vals.append(str(getattr(arm, "pose_position", "")))
            vals.append(str(getattr(arm, "deform_method", "")))
        except Exception:
            pass
        sig["armature_meta"] = _sha256("|".join(vals))
        # Bone hierarchy/rest transforms
        try:
            parts = []
            for b in arm.bones:
                try:
                    parts.append("B:" + (b.name or ""))
                    parts.append("P:" + (b.parent.name if b.parent else ""))
                    hl = getattr(b, "head_local", None)
                    tl = getattr(b, "tail_local", None)
                    parts.append("H:" + (_fmt_floats(hl) if hl is not None else ""))
                    parts.append("T:" + (_fmt_floats(tl) if tl is not None else ""))
                    parts.append("Roll:" + f"{float(getattr(b, 'roll', 0.0)):.6f}")
                    parts.append("Conn:" + ("1" if getattr(b, 'use_connect', False) else "0"))
                    parts.append("Deform:" + ("1" if getattr(b, 'use_deform', True) else "0"))
                    parts.append("InheritScale:" + str(getattr(b, 'inherit_scale', "")))
                except Exception:
                    pass
        except Exception:
            parts = []
        sig["armature_bones_hash"] = _sha256("|".join(parts))
        # Pose transforms and constraints
        try:
            pparts = []
            pose = getattr(obj, "pose", None)
            if pose is not None:
                for pb in pose.bones:
                    try:
                        pparts.append("PB:" + (pb.name or ""))
                        # Pose matrix in armature space
                        try:
                            pparts.append("Mat:" + _matrix_hash(pb.matrix))
                        except Exception:
                            pass
                        # rotation/location/scale
                        rm = getattr(pb, "rotation_mode", "")
                        pparts.append("RotMode:" + str(rm))
                        try:
                            if rm == 'QUATERNION':
                                q = getattr(pb, "rotation_quaternion", None)
                                if q is not None:
                                    pparts.append("Quat:" + _fmt_floats((q.w, q.x, q.y, q.z)))
                            else:
                                e = getattr(pb, "rotation_euler", None)
                                if e is not None:
                                    pparts.append("Euler:" + _fmt_floats((e.x, e.y, e.z)))
                        except Exception:
                            pass
                        try:
                            loc = getattr(pb, "location", None)
                            if loc is not None:
                                pparts.append("Loc:" + _fmt_floats((loc.x, loc.y, loc.z)))
                        except Exception:
                            pass
                        try:
                            sc = getattr(pb, "scale", None)
                            if sc is not None:
                                pparts.append("Scl:" + _fmt_floats((sc.x, sc.y, sc.z)))
                        except Exception:
                            pass
                        # Enhanced constraints
                        pparts.append(f"Cons:{_get_constraints_hash(pb.constraints)}")
                    except Exception:
                        pass
        except Exception:
            pparts = []
        sig["pose_bones_hash"] = _sha256("|".join(pparts))
        sig["modifiers"] = _get_modifiers_hash(obj)
        
    elif obj_type == "CURVE" and has_data:
        cu = obj.data  # bpy.types.Curve
        # Curve meta (shape and generation)
        vals = []
        try:
            vals.append(str(getattr(cu, "dimensions", "")))
            vals.append(str(getattr(cu, "twist_mode", "")))
            vals.append(f"{float(getattr(cu, 'twist_smoothing', 0.0)):.6f}")
            vals.append(f"{float(getattr(cu, 'resolution_u', 0)):.0f}")
            vals.append(f"{float(getattr(cu, 'resolution_v', 0)):.0f}")
            vals.append(f"{float(getattr(cu, 'render_resolution_u', 0)):.0f}")
            vals.append(f"{float(getattr(cu, 'render_resolution_v', 0)):.0f}")
            vals.append(f"{float(getattr(cu, 'bevel_depth', 0.0)):.6f}")
            vals.append(f"{float(getattr(cu, 'bevel_resolution', 0)):.0f}")
            vals.append(f"{float(getattr(cu, 'extrude', 0.0)):.6f}")
            vals.append(str(getattr(cu, "fill_mode", "")))
            vals.append(str(getattr(cu, "bevel_mode", "")))
            bev = getattr(cu, "bevel_object", None)
            vals.append(getattr(bev, "name", "") if bev else "")
            tp = getattr(cu, "taper_object", None)
            vals.append(getattr(tp, "name", "") if tp else "")
        except Exception:
            pass
        sig["curve_meta"] = _sha256("|".join(vals))
        # Control points hash
        try:
            parts = []
            for sp in cu.splines:
                st = getattr(sp, "type", "")
                parts.append(f"T:{st}")
                # Common attributes per spline
                try:
                    parts.append(f"CyclicU:{int(getattr(sp, 'use_cyclic_u', False))}")
                    parts.append(f"CyclicV:{int(getattr(sp, 'use_cyclic_v', False))}")
                    parts.append(f"OrderU:{int(getattr(sp, 'order_u', 0))}")
                    parts.append(f"OrderV:{int(getattr(sp, 'order_v', 0))}")
                    parts.append(f"ResU:{int(getattr(sp, 'resolution_u', 0))}")
                    parts.append(f"ResV:{int(getattr(sp, 'resolution_v', 0))}")
                except Exception:
                    pass
                if st == 'BEZIER':
                    for bp in getattr(sp, 'bezier_points', []) or []:
                        try:
                            hl = bp.handle_left
                            co = bp.co
                            hr = bp.handle_right
                            parts.extend([
                                _fmt_floats((hl.x, hl.y, hl.z)),
                                _fmt_floats((co.x, co.y, co.z)),
                                _fmt_floats((hr.x, hr.y, hr.z)),
                            ])
                        except Exception:
                            pass
                else:
                    for p in getattr(sp, 'points', []) or []:
                        try:
                            co = p.co  # 4D
                            parts.append(_fmt_floats((co.x, co.y, co.z, co.w)))
                        except Exception:
                            pass
        except Exception:
            parts = []
        sig["curve_points_hash"] = _sha256("|".join(parts))
        sig["modifiers"] = _get_modifiers_hash(obj)
    elif obj_type == "EMPTY":
        # Empty-specific properties
        sig["empty_display_type"] = obj.empty_display_type
        sig["empty_display_size"] = f"{obj.empty_display_size:.6f}"
        if obj.empty_display_type == 'IMAGE':
            sig["empty_image"] = obj.data.name if obj.data else ""
    else:
        # Other/unknown types - ensure all fields exist
        pass
    
    # Ensure all signature fields exist
    defaults = {
        "verts": 0, "edges": 0, "polygons": 0,
        "modifiers": "", "vgroups": "", "uv_meta": "",
        "shapekeys_meta": "", "shapekeys_values": "", "geo_hash": "",
        "light_meta": "", "camera_meta": "", "curve_meta": "",
        "curve_points_hash": "", "armature_meta": "",
        "armature_bones_hash": "", "pose_bones_hash": "",
        "lattice_meta": "", "lattice_points": "",
        "surface_meta": "", "surface_points": "",
        "meta_meta": "", "meta_elements": "",
        "font_meta": "", "volume_meta": "", "volume_grids": "",
        "pointcloud_count": 0, "pointcloud_attributes": "",
        "gpencil_meta": "", "gpencil_data": "",
        "empty_display_type": "", "empty_display_size": "",
        "empty_image": "", "instance_type": "",
        "instance_collection": "", "use_instance_vertices_rotation": 0,
        "use_instance_faces_scale": 0, "show_instancer_for_viewport": 0,
        "show_instancer_for_render": 0, "uv_color_data": "",
        "shapekeys_detailed": "",
    }
    
    for key, default in defaults.items():
        if key not in sig:
            sig[key] = default
    
    return sig


def _iter_objects_with_paths(root: bpy.types.Collection):
    """Yield (object, path_list) where path_list is the list of collection names from root's child to the collection holding the object.
    The root collection name is excluded from the path. Objects directly under root have an empty path_list.
    If an object is found in multiple branches, the first encountered path is used.
    """
    # DFS over collections recording path
    seen: set[int] = set()  # object id() seen to avoid duplicates

    def dfs(coll: bpy.types.Collection, path: List[str]):
        nonlocal seen
        for o in coll.objects:
            try:
                oid = id(o)
            except Exception:
                oid = None
            if oid is not None and oid in seen:
                continue
            if oid is not None:
                seen.add(oid)
            yield o, path
        for ch in coll.children:
            ch_name = getattr(ch, "name", "") or ""
            next_path = path + ([ch_name] if ch_name else [])
            yield from dfs(ch, next_path)

    yield from dfs(root, [])


def compute_collection_signature(coll: bpy.types.Collection) -> Tuple[Dict[str, Dict], str]:
    obj_sigs: Dict[str, Dict] = {}
    for obj, path in _iter_objects_with_paths(coll):
        sig = compute_object_signature(obj)
        if not sig["name"]:
            continue
        # Store collection path relative to provided root (exclude root name)
        try:
            # Normalize as 'A|B|C' to avoid ambiguity with '/'
            sig["collection_path"] = "|".join([p for p in path if p])
        except Exception:
            sig["collection_path"] = ""
        obj_sigs[sig["name"]] = sig
    # Overall collection hash: names + per-object quick fields
    parts: List[str] = []
    for nm in sorted(obj_sigs.keys()):
        s = obj_sigs[nm]
        parts.append("|".join([
            nm,
            s.get("parent", ""),
            s.get("type", ""),
            s.get("data_name", ""),
            s.get("transform", ""),
            s.get("dims", ""),
            str(s.get("verts", 0)),
            s.get("modifiers", ""),
            s.get("vgroups", ""),
            s.get("uv_meta", ""),
            s.get("shapekeys_meta", ""),
            s.get("shapekeys_values", ""),
            s.get("materials", ""),
            str(s.get("edges", 0)),
            str(s.get("polygons", 0)),
            s.get("geo_hash", ""),
            s.get("light_meta", ""),
            s.get("camera_meta", ""),
            s.get("collection_path", ""),
            s.get("curve_meta", ""),
            s.get("curve_points_hash", ""),
            s.get("armature_meta", ""),
            s.get("armature_bones_hash", ""),
            s.get("pose_bones_hash", ""),
        ]))
    collection_hash = _sha256("\n".join(parts))
    return obj_sigs, collection_hash


def _iter_collections_objects(coll: bpy.types.Collection):
    for o in coll.objects:
        yield o
    for c in coll.children:
        yield from _iter_collections_objects(c)




def derive_changed_set(curr_objs: Dict[str, Dict], prev_objs: Dict[str, Dict]) -> Tuple[bool, List[str]]:
    """Return (has_changes, changed_names).
    Includes:
    - Added and removed object names (set differences)
    - Modified objects among the intersection (attribute differences)
    """
    curr_names = set(curr_objs.keys())
    prev_names = set(prev_objs.keys())

    # Added/removed
    added = curr_names - prev_names
    removed = prev_names - curr_names

    changed_set = set()  # collect as set to avoid dups
    changed_set.update(added)
    changed_set.update(removed)

    # Modified within intersection - check ALL signature keys
    intersect = curr_names & prev_names
    for nm in intersect:
        a = curr_objs.get(nm, {})
        b = prev_objs.get(nm, {})
        
        # Compare all signature keys
        all_keys = set(a.keys()) | set(b.keys())
        for k in all_keys:
            if str(a.get(k, "")) != str(b.get(k, "")):
                changed_set.add(nm)
                break

    changed_list = sorted(changed_set)
    return (len(changed_list) > 0), changed_list
