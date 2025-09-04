# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


from .main.properties import register_properties, unregister_properties
from .main.operators import register_operators, unregister_operators
from .main.panel import register_panel, unregister_panel

import bpy
import os
import sys
import shutil
import subprocess
from typing import Tuple


class GitPrefUtils:
	def user_modules_dir(cls) -> str:
		try:
			path = bpy.utils.user_resource('SCRIPTS', path='modules', create=True)
			if path and os.path.isdir(path):
				return path
		except Exception:
			pass
		return os.path.expanduser("~")

	def pygit2_status(cls) -> Tuple[bool, str]:
		try:
			import importlib.util
			spec = importlib.util.find_spec('pygit2')
			if spec is None:
				return False, "Not installed"
			try:
				import pygit2  # type: ignore
				ver = getattr(pygit2, "__version__", "") or "installed"
				return True, str(ver)
			except Exception:
				return True, "installed"
		except Exception:
			return False, "Unknown"

	def blender_python_exe(cls) -> str:
		try:
			exe = bpy.app.binary_path_python
			if exe and os.path.exists(exe):
				return exe
		except Exception:
			pass
		return sys.executable or "python"

utils = GitPrefUtils()
modules_dir = utils.user_modules_dir()
status = utils.pygit2_status()
py = utils.blender_python_exe()

class GITBLEND_OT_install_pygit2(bpy.types.Operator):
	bl_idname = "gitblend.install_pygit2"
	bl_label = "Install pygit2"
	bl_description = "Install pygit2 into Blender's user modules folder"
	bl_options = {"INTERNAL"}

	def execute(self, context):
		# Ensure pip exists
		try:
			subprocess.run([py, "-m", "ensurepip", "--upgrade"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		except Exception:
			pass
		# Install pygit2 into the user modules dir
		try:
			result = subprocess.run([py, "-m", "pip", "install", "--upgrade", "pygit2", "--target", modules_dir],
									check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		except subprocess.CalledProcessError as e:
			self.report({'ERROR'}, f"pip failed: {e.stderr.decode(errors='ignore')[:200]}...")
			return {'CANCELLED'}
		except Exception as e:
			self.report({'ERROR'}, f"Install error: {e}")
			return {'CANCELLED'}

		# Make sure modules_dir is on sys.path for this session
		try:
			if modules_dir not in sys.path:
				sys.path.append(modules_dir)
		except Exception:
			pass

		ok, ver = status
		if ok:
			self.report({'INFO'}, f"pygit2 installed ({ver})")
		else:
			self.report({'WARNING'}, "pygit2 installation completed but not detected in session; restart Blender if needed.")
		return {'FINISHED'}


class GITBLEND_OT_uninstall_pygit2(bpy.types.Operator):
	bl_idname = "gitblend.uninstall_pygit2"
	bl_label = "Uninstall pygit2"
	bl_description = "Remove pygit2 from Blender's user modules folder"
	bl_options = {"INTERNAL"}

	def execute(self, context):
		removed_any = False
		try:
			# Remove package folder and dist-info folders
			targets = []
			for name in os.listdir(modules_dir):
				if name == "pygit2" or name.startswith("pygit2-") and (name.endswith(".dist-info") or name.endswith(".egg-info")):
					targets.append(os.path.join(modules_dir, name))
			for p in targets:
				try:
					if os.path.isdir(p):
						shutil.rmtree(p, ignore_errors=True)
					elif os.path.isfile(p):
						os.remove(p)
					removed_any = True
				except Exception:
					pass
		except Exception:
			pass

		if removed_any:
			self.report({'INFO'}, "pygit2 removed. You may need to restart Blender.")
		else:
			self.report({'INFO'}, "pygit2 not found in user modules.")
		return {'FINISHED'}


class GitBlendAddonPreferences(bpy.types.AddonPreferences):
	# Must match the top-level addon module name (folder name), e.g. 'git_blend'
	bl_idname = __package__

	def draw(self, context):
		layout = self.layout
		col = layout.column(align=True)
		modules_dir = utils.user_modules_dir()
		ok, ver = status
		col.label(text=f"User modules: {modules_dir}")
		col.label(text=f"pygit2: {'Installed ' + ver if ok else 'Not installed'}")
		row = col.row(align=True)
		row.operator("gitblend.install_pygit2", icon='IMPORT')
		row.operator("gitblend.uninstall_pygit2", icon='TRASH')

def register_prefs():
	bpy.utils.register_class(GITBLEND_OT_install_pygit2)
	bpy.utils.register_class(GITBLEND_OT_uninstall_pygit2)
	bpy.utils.register_class(GitBlendAddonPreferences)

def unregister_prefs():
	# Unregister in reverse dependency order
	for cls in (GitBlendAddonPreferences, GITBLEND_OT_uninstall_pygit2, GITBLEND_OT_install_pygit2):
		try:
			bpy.utils.unregister_class(cls)
		except Exception:
			pass

def register():
	register_properties()
	register_operators()
	register_panel()
	register_prefs()
	
def unregister():
	unregister_panel()
	unregister_operators()
	unregister_properties()
	unregister_prefs()
