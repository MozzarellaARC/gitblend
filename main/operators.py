import bpy  # type: ignore
import os
import subprocess
import tempfile
from datetime import datetime
from ..utils.git_utils import ensure_repo, add_and_commit, GitError

BLENDER_EXE = r"C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe"

class GITBLEND_OT_commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit the current changes to the Git repository"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 1) Collect all objects in the active scene (full-scene commit)
        object_names = [obj.name for obj in context.scene.objects]
        if not object_names:
            self.report({'WARNING'}, 'Scene has no objects to commit.')
            return {'CANCELLED'}

        # 2) Create a temporary copy of the current .blend as source for appending
        tmp_dir = tempfile.mkdtemp(prefix="gitblend_")
        source_blend = os.path.join(tmp_dir, "source.blend")
        try:
            res = bpy.ops.wm.save_as_mainfile(filepath=source_blend, copy=True)
            if res != {'FINISHED'}:
                self.report({'ERROR'}, 'Failed to create temporary source .blend')
                return {'CANCELLED'}
        except Exception as e:  # pragma: no cover - Blender context
            self.report({'ERROR'}, f'Error creating source blend: {e}')
            return {'CANCELLED'}

        # 3) Determine working repo root from current .blend and output path under .gitblend/commits
        current_file = bpy.data.filepath
        if not current_file:
            self.report({'ERROR'}, 'Please save the current .blend file before committing.')
            return {'CANCELLED'}
        working_root = os.path.dirname(current_file)
        dot_gitblend = os.path.join(working_root, '.gitblend')
        # Use a diffs directory to store delta .blends and manifests
        diffs_dir = os.path.join(dot_gitblend, 'diffs')
        os.makedirs(diffs_dir, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_blend = os.path.join(diffs_dir, f'diff_{stamp}.blend')
        manifest_path = os.path.join(diffs_dir, f'diff_{stamp}.json')

        # Find the most recent prior diff or commit as a baseline
        previous_path = None
        candidates = []
        # Prefer diffs (more recent runs), fall back to commits if present
        commits_dir = os.path.join(dot_gitblend, 'commits')
        try:
            if os.path.isdir(diffs_dir):
                for f in os.listdir(diffs_dir):
                    if f.lower().endswith('.blend'):
                        candidates.append(os.path.join(diffs_dir, f))
            if os.path.isdir(commits_dir):
                for f in os.listdir(commits_dir):
                    if f.lower().endswith('.blend'):
                        candidates.append(os.path.join(commits_dir, f))
            if candidates:
                previous_path = max(candidates, key=lambda p: os.path.getmtime(p))
        except Exception:
            previous_path = None

        # 4) Build path to headless script
        headless_script = os.path.join(os.path.dirname(__file__), 'headless_commit.py')
        if not os.path.exists(headless_script):
            self.report({'ERROR'}, f'Headless script missing: {headless_script}')
            return {'CANCELLED'}

        blender_exe = BLENDER_EXE
        if not os.path.exists(blender_exe):
            try:
                blender_exe = bpy.app.binary_path  # type: ignore[attr-defined]
            except Exception:
                blender_exe = BLENDER_EXE
        if not os.path.exists(blender_exe):
            self.report({'ERROR'}, f'Blender executable not found: {blender_exe}')
            return {'CANCELLED'}

        # 5) Launch Blender headless to append selected objects and save new .blend
        cmd = [
            blender_exe,
            "--background",
            "--factory-startup",
            "--python", headless_script,
            "--",
            "--source", source_blend,
            "--output", output_blend,
            "--manifest", manifest_path,
        ]
        if previous_path and os.path.exists(previous_path):
            cmd.extend(["--previous", previous_path])
        for name in object_names:
            cmd.extend(["--object", name])

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
        except Exception as e:  # pragma: no cover
            self.report({'ERROR'}, f'Failed to launch headless Blender: {e}')
            return {'CANCELLED'}

        if proc.returncode != 0:
            # Surface a small portion of both stderr and stdout for debugging
            err_tail = (proc.stderr or "").strip().splitlines()[-10:]
            out_tail = (proc.stdout or "").strip().splitlines()[-10:]
            details = " | ".join([*out_tail, *err_tail])
            self.report({'ERROR'}, f'Headless commit failed (code {proc.returncode}). {details}')
            return {'CANCELLED'}

        if not os.path.exists(output_blend):
            self.report({'ERROR'}, 'Commit output file was not created.')
            return {'CANCELLED'}

        # 6) Git + LFS: ensure repo and commit the new artifacts inside .gitblend
        try:
            ensure_repo(dot_gitblend)
            rel_output = os.path.relpath(output_blend, start=dot_gitblend)
            rel_manifest = os.path.relpath(manifest_path, start=dot_gitblend)
            msg = f"feat(git-blend): diff {os.path.basename(output_blend)}"
            add_and_commit(dot_gitblend, [rel_output, rel_manifest], msg)
        except GitError as ge:
            self.report({'WARNING'}, f'Git/LFS step failed: {ge}')
        except Exception as ge:
            self.report({'WARNING'}, f'Git/LFS unexpected error: {ge}')

        # Best-effort cleanup of temp files
        try:
            # Remove only the temp file to keep dir removal simple on Windows
            if os.path.exists(source_blend):
                os.remove(source_blend)
            # Attempt to remove the directory (will succeed if empty)
            os.rmdir(tmp_dir)
        except Exception:
            pass

        self.report({'INFO'}, f'Committed scene diff to {output_blend}')
        return {'FINISHED'}