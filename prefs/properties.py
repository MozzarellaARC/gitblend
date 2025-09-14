import bpy # type: ignore
from bpy.types import PropertyGroup


class GITBLEND_CommitEntry(PropertyGroup):
    hash: bpy.props.StringProperty(name="Hash", default="")  # type: ignore
    message: bpy.props.StringProperty(name="Message", default="")  # type: ignore
    timestamp: bpy.props.StringProperty(name="Timestamp", default="")  # type: ignore


class GITBLEND_Properties(bpy.types.PropertyGroup):
    commit_message: bpy.props.StringProperty(  # type: ignore
        name="Message",
        description="Commit message",
        default="",
        options={'TEXTEDIT_UPDATE'},
    )
    commits: bpy.props.CollectionProperty(type=GITBLEND_CommitEntry)  # type: ignore
    commits_index: bpy.props.IntProperty(name="Active Commit", default=-1)  # type: ignore