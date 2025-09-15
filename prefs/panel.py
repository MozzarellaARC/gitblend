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
    pass

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