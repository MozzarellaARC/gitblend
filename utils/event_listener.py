import bpy

def on_save_event_listener(self, context):
	print("Hello World!")

def invoke_save_event_listener():
	bpy.app.handlers.save_post.append(on_save_event_listener)