import bpy  # type: ignore

class GITBLEND_Properties(bpy.types.PropertyGroup):
    commit_message: bpy.props.StringProperty(
        name="Commit Message",
        description="Message for the commit",
        default=""
    )
    initialized: bpy.props.BoolProperty(
        name="Initialized",
        description="Whether Git Blend has been initialized in this project",
        default=False
    )