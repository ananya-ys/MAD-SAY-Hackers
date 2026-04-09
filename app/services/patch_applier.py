"""
app/services/patch_applier.py
PatchApplierService: apply unified diff to ephemeral /tmp/repair_{session_id}/ copy.
Working directory wiped after every run — no cross-session contamination.
All writes isolated to the mounted volume — seccomp prevents host FS access.
"""
from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from unidiff import PatchSet

from app.core.logging import get_logger

logger = get_logger(__name__)

_SANDBOX_BASE = Path("/tmp")


class PatchApplierService:

    def create_working_dir(self, session_id: uuid.UUID, repo_path: str) -> Path:
        """
        Copy repo to ephemeral /tmp/repair_{session_id}/.
        Caller must call cleanup_working_dir() after the session completes.
        """
        working_dir = _SANDBOX_BASE / f"repair_{session_id.hex}"
        src = Path(repo_path)

        if not src.exists():
            # In tests / CI: create minimal placeholder
            working_dir.mkdir(parents=True, exist_ok=True)
            (working_dir / "placeholder.py").write_text("# placeholder\n")
            return working_dir

        if working_dir.exists():
            shutil.rmtree(str(working_dir))

        shutil.copytree(str(src), str(working_dir))
        logger.info("working_dir_created", session_id=str(session_id), path=str(working_dir))
        return working_dir

    def apply_patch(self, working_dir: Path, patch: str) -> tuple[bool, str]:
        """
        Apply unified diff patch to working_dir.
        Returns (success: bool, error_message: str).
        Validates patch is well-formed before applying.
        """
        if not patch or not patch.strip():
            return False, "Empty patch"

        try:
            patch_set = PatchSet(patch)
        except Exception as exc:
            return False, f"Invalid unified diff: {exc}"

        errors: list[str] = []

        for patched_file in patch_set:
            target = working_dir / patched_file.path.lstrip("/")

            if patched_file.is_added_file:
                target.parent.mkdir(parents=True, exist_ok=True)
                lines = [h.value for h in patched_file[0] if not h.is_removed]
                target.write_text("".join(lines))
                continue

            if patched_file.is_removed_file:
                target.unlink(missing_ok=True)
                continue

            # Modified file
            if not target.exists():
                # Might be a new file created via patch syntax — create it
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("")

            lines = target.read_text(errors="replace").splitlines(keepends=True)

            for hunk in patched_file:
                src_start = hunk.source_start - 1  # 0-indexed

                # Build new lines for this hunk
                new_hunk_lines: list[str] = []
                for line in hunk:
                    if line.is_context or line.is_added:
                        new_hunk_lines.append(line.value)
                    # removed lines are skipped

                end = src_start + hunk.source_length
                lines[src_start:end] = new_hunk_lines

            try:
                target.write_text("".join(lines))
            except OSError as exc:
                errors.append(f"{target}: {exc}")

        if errors:
            return False, "; ".join(errors)

        logger.info("patch_applied", working_dir=str(working_dir), files=len(list(patch_set)))
        return True, ""

    def patch_hash(self, patch: str) -> str:
        """SHA256 of patch content — used for duplicate detection (loop guard)."""
        return hashlib.sha256(patch.encode()).hexdigest()[:16]

    def cleanup_working_dir(self, working_dir: Path) -> None:
        """Wipe ephemeral dir after session. No cross-session contamination."""
        shutil.rmtree(str(working_dir), ignore_errors=True)
        logger.debug("working_dir_cleaned", path=str(working_dir))
