import bpy

def on_save_event_listener(self, context):
	#TODO: Staging area
    pass

bpy.app.handlers.save_post.append(on_save_event_listener)