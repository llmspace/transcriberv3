"""
Cleanup: delete audio artifacts after job completion.
"""

import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_job_artifacts(job_workspace: Path, keep_debug: bool = False):
    """
    Delete job artifacts after completion (success or failure).

    Deletes: source/, normalized/, chunks/, transcripts/
    If keep_debug is True: preserves meta/ and Deepgram JSON responses.
    """
    if not job_workspace.exists():
        return

    dirs_to_delete = ['source', 'normalized', 'chunks']

    if not keep_debug:
        dirs_to_delete.append('transcripts')
        dirs_to_delete.append('meta')

    for dirname in dirs_to_delete:
        dir_path = job_workspace / dirname
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path)
                logger.debug("Deleted: %s", dir_path)
            except Exception as e:
                logger.warning("Failed to delete %s: %s", dir_path, e)

    # If not keeping debug, remove the entire workspace if empty
    if not keep_debug:
        try:
            if job_workspace.exists() and not any(job_workspace.iterdir()):
                job_workspace.rmdir()
                logger.debug("Removed empty workspace: %s", job_workspace)
        except Exception:
            pass
    else:
        # Even in debug mode, clean up source and normalized audio
        for dirname in ['source', 'normalized', 'chunks']:
            dir_path = job_workspace / dirname
            if dir_path.exists():
                try:
                    shutil.rmtree(dir_path)
                except Exception:
                    pass
