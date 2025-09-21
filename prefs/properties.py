import bpy
from bpy.props import (
    StringProperty,
)

class GITBLEND_Properties(bpy.types.PropertyGroup):
    commit_message: StringProperty(
        name="Commit Message",
        description="Message for the commit",
        default="Commit Message",
        maxlen=64
    )