# Git Blend Add-on

Change validation is performed before creating a new snapshot under `.gitblend`:

Order of checks (early exit on first difference):
- Name set equality (by original names)
- Transform equality (matrix_world), then origin position
- Bounding box dimensions equality
- Vertex count (for meshes)
- Modifier stack/type/name equality
- Vertex group names
- UV layers count and names
- Shapekey count and names
- UV coordinates (per-loop)
- Shapekey values and point counts
- Vertex weights per group (per-vertex)
- Vertex world-space positions (per-vertex)
- Shapekey point coordinates (per-vertex, non-Basis)

Snapshots store metadata `gitblend_orig_name` on objects/collections for robust matching across commits. If no differences are found against the last snapshot for the selected branch, the commit is skipped.

Ideas for additional validations:
- Custom properties (ID properties) on objects and meshes
- Materials: slot order, material names, and per-slot link types
- Armatures: bone hierarchies and constraints
- Constraints: types, targets, and key parameter values
- Geometry data hashes for edges/polygons to detect topology changes precisely
