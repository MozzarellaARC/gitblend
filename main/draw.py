import bpy
from datetime import datetime
from bpy.app.handlers import persistent


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
	
def register_draw():
	if _yant_on_save not in bpy.app.handlers.save_post:
		bpy.app.handlers.save_post.append(_yant_on_save)
		
def unregister_draw():
	if _yant_on_save in bpy.app.handlers.save_post:
		bpy.app.handlers.save_post.remove(_yant_on_save)