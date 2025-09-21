import bpy
from bpy.props import (
    StringProperty,
)

class GITBLEND_Commit_List(bpy.types.PropertyGroup):
    commit_id: StringProperty(
        name="Commit ID",
        description="Unique identifier for the commit",
        default=""
    )
    timestamp: StringProperty(
        name="Timestamp",
        description="Time when the commit was made",
        default=""
    )
    commit_message: StringProperty(
        name="Commit Message",
        description="Message associated with the commit",
        default=""
    )


class GITBLEND_Properties(bpy.types.PropertyGroup):
    message: StringProperty(
        name="Commit Message",
        description="Message for the commit",
        default="Commit Message",
        maxlen=64
    )