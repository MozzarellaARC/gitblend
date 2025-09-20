import bpy
import os
import json
import hashlib
import time
import filecmp
from datetime import datetime
from pathlib import Path


class GITBLEND_OT_Commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit current changes to git blend repository"
    bl_options = {'REGISTER', 'UNDO'}
   
   