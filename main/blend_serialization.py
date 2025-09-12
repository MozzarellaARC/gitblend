import bpy
import json
import os
from pathlib import Path

# Configuration for what data to include (whitelist approach)
INCLUDE_DATA_COLLECTIONS = [
    'objects',        # Scene objects (meshes, cameras, lights, etc.)
    'meshes',         # Mesh data
    'materials',      # Materials
    'textures',       # Textures
    'images',         # Image datablocks
    'curves',         # Curve objects
    'metaballs',      # Metaball objects
    'lights',         # Light objects
    'cameras',        # Camera objects
    'speakers',       # Speaker objects
    'armatures',      # Armature data
    'actions',        # Animation actions
    'particles',      # Particle systems
    'collections',    # Object collections
    'scenes',         # Scenes
    'worlds',         # World settings
    'node_groups',    # Node groups (shader/geometry/etc.)
    'fonts',          # Font data
    'grease_pencils', # Grease pencil data
    'volumes',        # Volume objects
    'hair_curves',    # Hair curve objects (if available)
    'shape_keys',     # Shape keys
    # Add more collections as needed
]

def discover_types_from_collections():
    """Dynamically discover all RNA types used in the included data collections."""
    discovered_types = set()
    
    print("Discovering types from data collections...")
    
    for collection_name in INCLUDE_DATA_COLLECTIONS:
        if hasattr(bpy.data, collection_name):
            try:
                collection = getattr(bpy.data, collection_name)
                
                # Add the collection's own type
                if hasattr(collection, 'rna_type'):
                    discovered_types.add(collection.rna_type.identifier)
                
                # Analyze items in the collection
                if hasattr(collection, '__iter__'):
                    for item in collection:
                        # Add the item's type
                        if hasattr(item, 'rna_type'):
                            discovered_types.add(item.rna_type.identifier)
                        
                        # Recursively discover types from item properties
                        discovered_types.update(discover_types_from_object(item))
                        
            except Exception as e:
                print(f"  Warning: Could not analyze collection '{collection_name}': {e}")
    
    print(f"  Discovered {len(discovered_types)} unique types")
    return discovered_types

def discover_types_from_object(obj, visited=None, max_depth=2, current_depth=0):
    """Recursively discover RNA types from an object's properties."""
    if visited is None:
        visited = set()
    
    if current_depth >= max_depth or id(obj) in visited:
        return set()
    
    visited.add(id(obj))
    discovered_types = set()
    
    # Add the object's own type
    if hasattr(obj, 'rna_type'):
        discovered_types.add(obj.rna_type.identifier)
    
    # Analyze RNA properties
    if hasattr(obj, 'bl_rna') and hasattr(obj.bl_rna, 'properties'):
        for prop in obj.bl_rna.properties:
            try:
                if prop.type == 'POINTER':
                    # Add pointer target type
                    if hasattr(prop, 'fixed_type'):
                        discovered_types.add(prop.fixed_type.identifier)
                    
                    # Analyze the actual pointed object
                    value = getattr(obj, prop.identifier, None)
                    if value is not None and hasattr(value, 'rna_type'):
                        discovered_types.add(value.rna_type.identifier)
                        # Recursively analyze the pointed object
                        discovered_types.update(discover_types_from_object(value, visited, max_depth, current_depth + 1))
                
                elif prop.type == 'COLLECTION':
                    # Add collection item type
                    if hasattr(prop, 'fixed_type'):
                        discovered_types.add(prop.fixed_type.identifier)
                    
                    # Analyze collection items
                    try:
                        collection = getattr(obj, prop.identifier, None)
                        if collection and hasattr(collection, '__iter__'):
                            # Limit analysis to avoid performance issues
                            for i, item in enumerate(collection):
                                if i >= 10:  # Analyze max 10 items per collection
                                    break
                                if hasattr(item, 'rna_type'):
                                    discovered_types.add(item.rna_type.identifier)
                                # Recursively analyze collection items
                                discovered_types.update(discover_types_from_object(item, visited, max_depth, current_depth + 1))
                    except:
                        pass  # Skip inaccessible collections
                        
            except Exception:
                continue  # Skip problematic properties
    
    return discovered_types

def serialize_object_properties(obj, max_depth=2, current_depth=0, exclude_props=None):
    """Recursively serialize all properties of a Blender object."""
    if current_depth >= max_depth:
        return {"_truncated": "Max depth reached"}
    
    if exclude_props is None:
        exclude_props = {
            'rna_type', 'bl_rna', '__doc__', '__module__', '__slots__',
            # Temporal/volatile properties that change frequently
            'update_tag', 'is_updated', 'is_updated_data', 'tag', 
            # Memory/cache related properties
            'id_data', 'library', 'library_weak_reference',
            # System/internal properties  
            'session_uuid', 'original', 'override_library',
            # Animation/frame dependent properties that may be unstable
            'is_evaluated', 'evaluated_get'
        }
    
    result = {}
    
    # Get the RNA properties if available
    if hasattr(obj, 'bl_rna') and hasattr(obj.bl_rna, 'properties'):
        for prop in obj.bl_rna.properties:
            if (prop.identifier in exclude_props or 
                prop.identifier.startswith('bl_') or
                # Filter out commonly volatile property patterns
                'update' in prop.identifier.lower() or
                'cache' in prop.identifier.lower() or
                'tag' in prop.identifier.lower() or
                'uuid' in prop.identifier.lower() or
                'time' in prop.identifier.lower()):
                continue
                
            try:
                value = getattr(obj, prop.identifier)
                
                if prop.type == 'POINTER':
                    if value is not None:
                        # Create stable reference with name and type
                        if hasattr(value, 'name') and value.name:
                            # Include both type and name for stable reference
                            result[prop.identifier] = {
                                "_type": type(value).__name__,
                                "_name": value.name,
                                "_ref": f"<{type(value).__name__}: {value.name}>"
                            }
                        else:
                            # Fallback for objects without names
                            result[prop.identifier] = {
                                "_type": type(value).__name__,
                                "_ref": f"<{type(value).__name__}>"
                            }
                    else:
                        result[prop.identifier] = None
                        
                elif prop.type == 'COLLECTION':
                    if hasattr(value, '__len__'):
                        collection_info = {
                            "_collection_type": type(value).__name__,
                            "count": len(value)
                        }
                        
                        # For small collections, serialize the items with deterministic ordering
                        if len(value) <= 20 and current_depth < max_depth - 1:
                            items = []
                            
                            # Sort items deterministically by name (or fallback to string representation)
                            try:
                                sorted_items = sorted(value, key=lambda x: getattr(x, 'name', str(x)))
                            except (TypeError, AttributeError):
                                # Fallback if sorting fails
                                sorted_items = list(value)
                                
                            for item in sorted_items:
                                if hasattr(item, 'name'):
                                    # Recursively serialize collection items (like modifiers)
                                    item_data = serialize_object_properties(item, max_depth, current_depth + 1, exclude_props)
                                    item_data["_name"] = item.name
                                    items.append(item_data)
                                else:
                                    items.append(str(item))
                            collection_info["items"] = items
                        
                        result[prop.identifier] = collection_info
                    else:
                        result[prop.identifier] = f"<Collection: {type(value).__name__}>"
                        
                elif prop.type in {'INT', 'FLOAT', 'BOOLEAN', 'STRING', 'ENUM'}:
                    result[prop.identifier] = value
                    
                elif hasattr(value, '__len__') and not isinstance(value, str):
                    # Handle vectors, arrays, etc.
                    try:
                        if len(value) <= 16:  # Reasonable size limit
                            result[prop.identifier] = list(value)
                        else:
                            result[prop.identifier] = f"<Array[{len(value)}]>"
                    except:
                        result[prop.identifier] = str(value)
                        
                else:
                    result[prop.identifier] = str(value)
                    
            except Exception as e:
                result[prop.identifier] = f"<Error: {str(e)}>"
    
    return result

def dump_rna_struct(struct, max_depth=3, current_depth=0):
    """Dump RNA struct information to a dictionary."""
    if current_depth >= max_depth:
        return {"_truncated": "Max depth reached"}
    
    data = {
        "name": struct.name,
        "identifier": struct.identifier,
        # Skip description field to reduce clutter
        "properties": {}
    }
    
    # Add base class info if available
    if hasattr(struct, 'base') and struct.base:
        data["base"] = struct.base.identifier
    
    # Dump properties
    for prop in struct.properties:
        # if prop.identifier == 'rna_type':
        #     continue  # Skip meta property
        
        # Skip internal Blender properties and description-related properties
        if (prop.identifier.startswith('bl_') or 
            'description' in prop.identifier.lower()):
            continue
            
        prop_data = {
            "type": prop.type,
            "subtype": prop.subtype if hasattr(prop, 'subtype') else None,
            # Skip description field to reduce clutter
            "is_readonly": prop.is_readonly,
            "is_required": prop.is_required if hasattr(prop, 'is_required') else False,
        }
        
        # Add type-specific information
        if prop.type in {'INT', 'FLOAT'}:
            if hasattr(prop, 'hard_min'):
                prop_data["min"] = prop.hard_min
            if hasattr(prop, 'hard_max'):
                prop_data["max"] = prop.hard_max
        elif prop.type == 'ENUM':
            if hasattr(prop, 'enum_items'):
                prop_data["items"] = [item.identifier for item in prop.enum_items]
        elif prop.type == 'POINTER':
            if hasattr(prop, 'fixed_type'):
                prop_data["pointer_type"] = prop.fixed_type.identifier
        elif prop.type == 'COLLECTION':
            if hasattr(prop, 'fixed_type'):
                prop_data["collection_type"] = prop.fixed_type.identifier
        
        data["properties"][prop.identifier] = prop_data
    
    return data

def dump_all_rna():
    """Dump bpy.data collections from Blender."""
    print("Starting bpy.data dump...")
    
    rna_data = {
        "blender_version": bpy.app.version_string,
        "api_version": list(bpy.app.version),
        "data_collections": {},
        "summary": {
            "total_collections": 0,
            "total_items": 0,
            "included_collections": []
        }
    }
    
    # Dump only specified bpy.data collections
    print("Dumping bpy.data collections...")
    for collection_name in sorted(dir(bpy.data)):
        if not collection_name.startswith('_'):
            # Check if this collection should be included
            if collection_name in INCLUDE_DATA_COLLECTIONS:
                try:
                    collection = getattr(bpy.data, collection_name)
                    if hasattr(collection, 'rna_type'):
                        collection_count = len(collection) if hasattr(collection, '__len__') else 0
                        
                        collection_info = {
                            "type": collection.rna_type.identifier,
                            "count": collection_count
                        }
                        
                        # Sample items if collection is not empty - use deterministic ordering
                        if hasattr(collection, '__iter__') and collection_count > 0:
                            items_sample = []
                            
                            # Sort items deterministically by name (or fallback to string representation)
                            try:
                                sorted_items = sorted(collection, key=lambda x: getattr(x, 'name', str(x)))
                            except (TypeError, AttributeError):
                                # Fallback if sorting fails - convert to list to ensure consistent order
                                sorted_items = list(collection)
                            
                            for i, item in enumerate(sorted_items):
                                if i >= 5:  # Reduced to 5 items due to more detailed data
                                    break
                                
                                # Use generic serialization for all items
                                item_data = serialize_object_properties(item, max_depth=3)
                                
                                # Ensure we have basic identification
                                if hasattr(item, 'name'):
                                    item_data["_name"] = item.name
                                item_data["_type"] = type(item).__name__
                                
                                items_sample.append(item_data)
                            
                            collection_info["sample_items"] = items_sample
                        
                        rna_data["data_collections"][collection_name] = collection_info
                        rna_data["summary"]["included_collections"].append(collection_name)
                        rna_data["summary"]["total_collections"] += 1
                        rna_data["summary"]["total_items"] += collection_count
                        
                        print(f"  ✓ {collection_name}: {collection_count} items")
                        
                except Exception as e:
                    rna_data["data_collections"][collection_name] = {"error": str(e)}
                    print(f"  ✗ {collection_name}: Error - {str(e)}")
            else:
                print(f"  - Skipping: {collection_name}")
    
    return rna_data

def export_json():
    """Main function to dump bpy.data and save to JSON."""
    
    # Get the current blend file path
    blend_filepath = bpy.data.filepath
    
    if not blend_filepath:
        print("Error: Please save the blend file first!")
        return {'CANCELLED'}
    
    # Create JSON filename in the same directory
    blend_dir = os.path.dirname(blend_filepath)
    blend_name = Path(blend_filepath).stem
    json_filepath = os.path.join(blend_dir, f"{blend_name}_data_dump.json")
    
    try:
        # Dump bpy.data collections
        data_dump = dump_all_rna() 
        
        # Save to JSON file
        print(f"Saving bpy.data to: {json_filepath}")
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(data_dump, f, indent=2, ensure_ascii=False, sort_keys=True, default=str)
        
        print(f"✓ bpy.data successfully dumped to: {json_filepath}")
        print(f"  - Collections included: {data_dump['summary']['total_collections']}")
        print(f"  - Total data items: {data_dump['summary']['total_items']}")
        
        # Show info in Blender's info area
        def show_info(self, context):
            self.layout.label(text=f"bpy.data saved to: {os.path.basename(json_filepath)}")
        
        bpy.context.window_manager.popup_menu(show_info, title="Data Dump Complete", icon='INFO')
        
    except Exception as e:
        print(f"✗ Error dumping bpy.data: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'CANCELLED'}
    
    return {'FINISHED'}