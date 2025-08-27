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
from datetime import datetime
from bpy.app.handlers import persistent

from .main.properties import register_properties, unregister_properties
from .main.operators import register_operators, unregister_operators
from .main.panel import register_panel, unregister_panel

bl_info = {
	"name": "Yant",
	"author": "mzxc",
	"version": (1, 0, 0),
	"blender": (4, 2, 0),
	"location": "View3D > Sidebar > YANT",
	"description": "Records save events and shows them in a panel",
	"category": "System",
}


@persistent
def _yant_on_save(dummy):
	scene = bpy.context.scene
	props = getattr(scene, "yant_props", None)
	if not props:
		return
	ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	path = bpy.data.filepath
	item = props.save_events.add()
	item.timestamp = ts
	item.filepath = path
	_yant_request_redraw()


def _yant_request_redraw():
	"""Tag UI areas for redraw so the panel updates immediately."""
	wm = getattr(bpy.context, "window_manager", None)
	if wm:
		for window in wm.windows:
			screen = window.screen
			for area in screen.areas:
				# Redraw all areas; cheap enough and reliable
				try:
					area.tag_redraw()
				except Exception:
					pass
	# Optional: try a redraw timer as a fallback
	try:
		bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
	except Exception:
		pass


def register():
	register_properties()
	register_operators()
	register_panel()
	if _yant_on_save not in bpy.app.handlers.save_post:
		bpy.app.handlers.save_post.append(_yant_on_save)


def unregister():
	if _yant_on_save in bpy.app.handlers.save_post:
		bpy.app.handlers.save_post.remove(_yant_on_save)
	unregister_panel()
	unregister_operators()
	unregister_properties()
