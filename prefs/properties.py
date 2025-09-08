import bpy # type: ignore

class GITBLEND_Properties(bpy.types.PropertyGroup):
    commit_message: bpy.props.StringProperty(  # type: ignore
        name="Message",
        description="Commit message",
        default="",
        options={'TEXTEDIT_UPDATE'},
    )