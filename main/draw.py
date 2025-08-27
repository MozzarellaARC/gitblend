import bpy
from bpy.app.handlers import persistent
from .utils import now_str, request_redraw


@persistent
def _gitblend_on_save(dummy):
	scene = bpy.context.scene
	props = getattr(scene, "gitblend_props", None)
	if not props:
		return
	ts = now_str()
	path = bpy.data.filepath
	item = props.save_events.add()
	item.timestamp = ts
	item.filepath = path
	request_redraw()
	
def register_draw():
	if _gitblend_on_save not in bpy.app.handlers.save_post:
		bpy.app.handlers.save_post.append(_gitblend_on_save)
		
def unregister_draw():
	if _gitblend_on_save in bpy.app.handlers.save_post:
		bpy.app.handlers.save_post.remove(_gitblend_on_save)