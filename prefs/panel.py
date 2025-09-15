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
            row = layout.row(align=True)
            split = row.split(factor=0.55, align=True)
            left = split.row(align=True)
            left.label(text=stash_entry.name, icon='OBJECT_DATAMODE')
            if stash_entry.original and stash_entry.original != stash_entry.name:
                left.label(text=stash_entry.original, icon='DOT')
            right = split.row(align=True)
            op_a = right.operator("gitblend.stash_append", text="", icon='IMPORT')
            op_a.names = stash_entry.name
            op_d = right.operator("gitblend.stash_delete", text="", icon='TRASH')
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
            col_actions = row_list.column(align=True)
            if props.stash_index >= 0 and props.stash_index < len(props.stash_items):
                active_name = props.stash_items[props.stash_index].name
                op_a = col_actions.operator("gitblend.stash_append", text="Append", icon='IMPORT')
                op_a.names = active_name
                op_d = col_actions.operator("gitblend.stash_delete", text="Delete", icon='TRASH')
                op_d.names = active_name
            else:
                col_actions.label(text="Select", icon='INFO')