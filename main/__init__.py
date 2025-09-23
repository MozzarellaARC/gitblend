import bpy # type: ignore

from .checkout import (
	GITBLEND_OT_Checkout,
	GITBLEND_OT_PreCheckout
)

from .commit import (
	GITBLEND_OT_Commit
)

from .refresh import (
	GITBLEND_OT_Refresh,
)

from .stage import (
	stage_handler)

cls = [
	GITBLEND_OT_PreCheckout,
	GITBLEND_OT_Checkout,
	GITBLEND_OT_Commit,
	GITBLEND_OT_Refresh,
]

def register_operators():
	for c in cls:
		try:
			bpy.utils.register_class(c)
		except ValueError:
			# Class is already registered, skip silently
			pass
		except Exception as e:
			print(f"Error registering operator {c.__name__}: {e}")
	
	# Stage data and register save handler
	if stage_handler not in bpy.app.handlers.save_post:
		bpy.app.handlers.save_post.append(stage_handler)

def unregister_operators():
	for c in reversed(cls):
		try:
			bpy.utils.unregister_class(c)
		except RuntimeError:
			# Class is not registered, skip silently
			pass
		except Exception as e:
			print(f"Error unregistering operator {c.__name__}: {e}")
	
	# Unregister save handler
	if stage_handler in bpy.app.handlers.save_post:
		bpy.app.handlers.save_post.remove(stage_handler)

__all__ = (
	"register_operators",
	"unregister_operators",
)