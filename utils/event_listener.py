import bpy

def on_save_event_listener(self, context):
	#TODO: Staging area
    pass

def invoke_save_event_listener():
	return bpy.app.handlers.save_post.remove(on_save_event_listener)