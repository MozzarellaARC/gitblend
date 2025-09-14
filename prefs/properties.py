import bpy  # type: ignore


class GITBLEND_CommitItem(bpy.types.PropertyGroup):
    """Single commit entry stored in the scene collection."""
    hash: bpy.props.StringProperty(name="Hash", default="")  # type: ignore
    author: bpy.props.StringProperty(name="Author", default="")  # type: ignore
    date: bpy.props.StringProperty(name="Date", default="")  # type: ignore
    message: bpy.props.StringProperty(name="Message", default="")  # type: ignore


class GITBLEND_Properties(bpy.types.PropertyGroup):
    commit_message: bpy.props.StringProperty(  # type: ignore
        name="Message",
        description="Commit message",
        default="",
        options={'TEXTEDIT_UPDATE'},
    )

    commit_history: bpy.props.CollectionProperty(type=GITBLEND_CommitItem)  # type: ignore
    commit_history_index: bpy.props.IntProperty(default=0)  # type: ignore
