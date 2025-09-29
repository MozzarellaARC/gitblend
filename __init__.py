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
from . import utils as utils_module
from .main.stage import stage_obj_handler

def register():
	prefs_module.register_prefs()
	main_module.register_operators()
	utils_module.register_utils()
	for handler in list(bpy.app.handlers.save_post):
		if (
			getattr(handler, "__name__", None) == stage_obj_handler.__name__
			and getattr(handler, "__module__", None) == stage_obj_handler.__module__
		):
			bpy.app.handlers.save_post.remove(handler)
	bpy.app.handlers.save_post.append(stage_obj_handler)

def unregister():
	utils_module.unregister_utils()
	main_module.unregister_operators()
	prefs_module.unregister_prefs()
	for handler in list(bpy.app.handlers.save_post):
		if (
			getattr(handler, "__name__", None) == stage_obj_handler.__name__
			and getattr(handler, "__module__", None) == stage_obj_handler.__module__
		):
			bpy.app.handlers.save_post.remove(handler)
	
