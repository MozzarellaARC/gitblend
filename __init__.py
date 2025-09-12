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

import bpy
from . import prefs as prefs_module
from . import main as main_module
from pathlib import Path

class GITBLEND_Preferences(bpy.types.AddonPreferences):
	bl_idname = __name__

	# Define your preferences properties here
	my_property: bpy.props.StringProperty(name="My Property", default="Default Value")

	def draw(self, context):
		layout = self.layout
		
		# jsondiff module management
		box = layout.box()
		box.label(text="JSON Diff Module Management")
		
		row = box.row()
		row.operator("gitblend.check_jsondiff")
		
		row = box.row()
		row.operator("gitblend.install_jsondiff")
		row.operator("gitblend.uninstall_jsondiff")

def register():
	prefs_module.register_prefs()
	bpy.utils.register_class(GITBLEND_Preferences)
	main_module.register_operators()
	
def unregister():
	main_module.unregister_operators()
	bpy.utils.unregister_class(GITBLEND_Preferences)
	prefs_module.unregister_prefs()
