import bpy # type: ignore

class GITBLEND_UL_commit_history(bpy.types.UIList):
    """UIList showing commit history entries."""
    bl_idname = "GITBLEND_UL_commit_history"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):  # noqa: D401
        commit = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            # Truncate hash for display
            short_hash = commit.hash[:8] if commit.hash else "<none>"
            row.label(text=short_hash, icon='FILE_BLEND')
            # Show timestamp (fallback to blank if missing)
            ts = getattr(commit, 'timestamp', '') or ''
            # Keep timestamp fixed width for alignment (YYYY-MM-DD HH:MM:SS = 19 chars)
            row.label(text=ts)
            # Remaining space for message
            row.label(text=commit.message[:60])
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=commit.hash[:8])

    def filter_items(self, context, data, propname):  # noqa: D401
        # No filtering yet
        items = getattr(data, propname)
        flt_flags = [self.bitflag_filter_item] * len(items)
        flt_neworder = []
        return flt_flags, flt_neworder

class GITBLEND_UL_stash_objects(bpy.types.UIList):
    bl_idname = "GITBLEND_UL_stash_objects"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):  # type: ignore
        stash_entry = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Layout: [Object Name] [UID] ....buttons
            row = layout.row(align=True)
            col_name = row.row(align=True)
            # Prefer original (base) name if available
            base_name = stash_entry.original if getattr(stash_entry, 'original', '') else stash_entry.name
            # Determine icon based on actual object type in the stash scene
            icon_name = 'OBJECT_DATAMODE'
            try:
                from ..main.stash import STASH_SCENE_NAME  # type: ignore
                scene = bpy.data.scenes.get(STASH_SCENE_NAME)
                obj = scene.objects.get(stash_entry.name) if scene else None  # type: ignore
                obj_type = getattr(obj, 'type', '') if obj else ''
                _type_icon_map = {
                    'MESH': 'OUTLINER_OB_MESH',
                    'ARMATURE': 'OUTLINER_OB_ARMATURE',
                    'CURVE': 'OUTLINER_OB_CURVE',
                    'CAMERA': 'OUTLINER_OB_CAMERA',
                    'LIGHT': 'OUTLINER_OB_LIGHT',
                    'EMPTY': 'OUTLINER_OB_EMPTY',
                    'LATTICE': 'OUTLINER_OB_LATTICE',
                    'GPENCIL': 'OUTLINER_OB_GREASEPENCIL',
                    'LIGHT_PROBE': 'OUTLINER_OB_LIGHTPROBE',
                    'VOLUME': 'OUTLINER_OB_VOLUME',
                    'POINTCLOUD': 'OUTLINER_OB_POINTCLOUD',
                    'SURFACE': 'OUTLINER_OB_SURFACE',
                    'META': 'OUTLINER_OB_META',
                    'SPEAKER': 'OUTLINER_OB_SPEAKER',
                }
                icon_name = _type_icon_map.get(obj_type, icon_name)
            except Exception:
                pass
            col_name.label(text=base_name, icon=icon_name)
            col_uid = row.row(align=True)
            try:
                col_uid.ui_units_x = 8.0
            except Exception:
                pass
            uid_txt = getattr(stash_entry, 'uid', '') or ''
            col_uid.label(text=uid_txt, icon='DOT')
            # Spacer to push buttons
            row.separator()
            buttons_row = row.row(align=True)
            buttons_row.alignment = 'RIGHT'
            try:
                buttons_row.ui_units_x = 3.0
            except Exception:
                pass
            op_a = buttons_row.operator("gitblend.stash_append", text="", icon='IMPORT')
            op_a.names = stash_entry.name
            op_d = buttons_row.operator("gitblend.stash_delete", text="", icon='TRASH')
            op_d.names = stash_entry.name
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=stash_entry.name[:8])

    def filter_items(self, context, data, propname):  # type: ignore
        items = getattr(data, propname)
        flt_flags = [self.bitflag_filter_item] * len(items)
        flt_neworder = []
        return flt_flags, flt_neworder


class GITBLEND_Panel(bpy.types.Panel):
    bl_idname = "GB_PT_main_panel"
    bl_label = "Git Blend"
    bl_category = ".gitblend"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        props = context.scene.gitblend_props
        col = layout.column(align=True)
        col.label(text="Commit History:")
        col.template_list("GITBLEND_UL_commit_history", "", props, "commits", props, "commits_index", rows=5)

        # Initialization section
        box_init = layout.box()
        box_init.label(text="Repository Setup")
        
        from ..main.initialize import is_gitblend_initialized, populate_ui_from_metadata  # type: ignore
        blend_path = bpy.data.filepath
        
        # Determine current state
        blend_saved = bool(blend_path)
        gitblend_initialized = False
        history_populated = bool(props.commits)
        
        if blend_saved:
            try:
                from pathlib import Path
                gitblend_initialized = is_gitblend_initialized(Path(blend_path).resolve().parent)
                
                # Auto-sync if .gitblend exists but history is not populated
                if gitblend_initialized and not history_populated:
                    try:
                        populate_ui_from_metadata(context)
                        history_populated = bool(props.commits)  # Update status after auto-sync
                    except Exception:
                        pass  # Silently fail auto-sync, user can manually sync
            except Exception:
                # Handle any path resolution errors
                blend_saved = False
        
        # Create the row for initialization controls
        row_init = box_init.row()
        
        if not blend_saved:
            # Blend file not saved
            row_init.label(text="Please save .blend file first", icon='ERROR')
        elif not gitblend_initialized:
            # Blend file saved but .gitblend not initialized
            row_init.operator("gitblend.initialize", text="Initialize", icon='FILE_NEW')
        elif gitblend_initialized and not history_populated:
            # .gitblend exists but history not loaded in UI (auto-sync failed)
            row_init.operator("gitblend.initialize", text="Sync", icon='FILE_REFRESH')
        else:
            # Everything is set up
            row_init.label(text="Initialized", icon='CHECKMARK')

        # Show commit controls if initialized
        if gitblend_initialized:
            box = layout.box()
            box.prop(props, "commit_message", text="Message")
            row = box.row(align=True)
            row.operator("gitblend.commit", text="Commit", icon='FILE_TICK')
        elif blend_saved and not gitblend_initialized:
            # Only show "Not initialized" warning if blend file is saved but not initialized
            warn_box = layout.box()
            warn_box.label(text="Not initialized", icon='ERROR')
        # Future buttons: diff, checkout etc.

        layout.separator()
        layout.operator("gb.bpy_serde", text="Serialize bpy into json", icon='DUPLICATE')

                # Stash Section (collapsible)
        layout.separator()
        box = layout.box()
        header_row = box.row()
        icon = 'TRIA_DOWN' if props.stash_show else 'TRIA_RIGHT'
        header_row.prop(props, "stash_show", text="Stash", emboss=False, icon=icon)
        if props.stash_show:
            inner = box.column(align=True)
            row_head = inner.row(align=True)
            row_head.operator("gitblend.stash_add", icon='EXPORT', text="Stash Selected")
            row_head.operator("gitblend.stash_refresh", icon='FILE_REFRESH', text="")
            # Visual separation between action buttons and list
            inner.separator()
            row_list = inner.row()
            row_list.template_list(
                "GITBLEND_UL_stash_objects",
                "",
                props,
                "stash_items",
                props,
                "stash_index",
                rows=4,
            )