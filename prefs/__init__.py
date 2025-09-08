import bpy

from .properties import (
	GITBLEND_Properties,
	GITBLEND_StringItem,
	GITBLEND_ChangeLogEntry,
)

__all__ = (
	"register_properties",
	"unregister_properties",
)


def _safe_register(cls):
	try:
		bpy.utils.register_class(cls)
	except ValueError:
		# Already registered; ignore to prevent noisy errors during dev reloads
		pass


def _safe_unregister(cls):
	try:
		bpy.utils.unregister_class(cls)
	except RuntimeError:
		pass
	except ValueError:
		pass


def register_properties():
	# Register PropertyGroups first
	_safe_register(GITBLEND_ChangeLogEntry)
	_safe_register(GITBLEND_StringItem)
	_safe_register(GITBLEND_Properties)

	# Attach to Scene once
	if not hasattr(bpy.types.Scene, "gitblend_props"):
		bpy.types.Scene.gitblend_props = bpy.props.PointerProperty(type=GITBLEND_Properties)


def unregister_properties():
	# Remove Scene property first to drop references
	if hasattr(bpy.types.Scene, "gitblend_props"):
		try:
			del bpy.types.Scene.gitblend_props
		except Exception:
			pass
	# Unregister PropertyGroups (reverse order)
	_safe_unregister(GITBLEND_Properties)
	_safe_unregister(GITBLEND_StringItem)
	_safe_unregister(GITBLEND_ChangeLogEntry)
