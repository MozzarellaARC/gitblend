"""
Base operator class and common operator utilities.
Reduces duplication in operator classes.
"""
import bpy
from .utils import sanitize_save_path, get_props, request_redraw
from .manager_collection import get_dotgitblend_collection


class GitBlendOperatorMixin:
    """Mixin class providing common functionality for GitBlend operators."""
    
    def validate_environment(self, context) -> tuple[bool, str]:
        """Validate that the environment is ready for GitBlend operations.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if file is saved in valid location
        ok, _, err = sanitize_save_path()
        if not ok:
            return False, err
        
        # Check if .gitblend collection exists
        scene = context.scene
        if not get_dotgitblend_collection(scene):
            return False, "'.gitblend' collection does not exist. Click Initialize first."
        
        return True, ""
    
    def get_props_or_fail(self, context):
        """Get GitBlend properties or report error and return None."""
        props = get_props(context)
        if not props:
            self.report({'ERROR'}, "GITBLEND properties not found")
            return None
        return props
    
    def finish_with_redraw(self, message: str, message_type: str = 'INFO'):
        """Complete operation with message and UI redraw."""
        request_redraw()
        self.report({message_type}, message)
        return {'FINISHED'}
    
    def cancel_with_message(self, message: str, message_type: str = 'ERROR'):
        """Cancel operation with message."""
        self.report({message_type}, message)
        return {'CANCELLED'}


class GitBlendBaseOperator(bpy.types.Operator, GitBlendOperatorMixin):
    """Base class for GitBlend operators with common functionality."""
    bl_options = {'INTERNAL'}
    
    def execute(self, context):
        """Override this method in subclasses."""
        raise NotImplementedError("Subclasses must implement execute method")


class GitBlendValidatedOperator(GitBlendBaseOperator):
    """Base operator that automatically validates environment before execution."""
    
    def execute(self, context):
        # Validate environment
        is_valid, error_msg = self.validate_environment(context)
        if not is_valid:
            return self.cancel_with_message(error_msg)
        
        # Get properties
        props = self.get_props_or_fail(context)
        if props is None:
            return {'CANCELLED'}
        
        # Execute main logic
        return self.execute_validated(context, props)
    
    def execute_validated(self, context, props):
        """Override this method in subclasses. Environment and props are guaranteed valid."""
        raise NotImplementedError("Subclasses must implement execute_validated method")
