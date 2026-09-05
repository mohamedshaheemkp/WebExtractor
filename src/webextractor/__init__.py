"""
WebExtractor package.
"""
import sys
import tempfile

if sys.platform == "win32":
    # Python 3.13 on Windows applies restrictive DACL when mode is 0o700 in tempfile.mkdtemp,
    # causing WinError 5 PermissionError when child directories are created in temporary folders.
    _orig_mkdir = tempfile._os.mkdir

    def _safe_temp_mkdir(path, mode=0o777, *args, **kwargs):
        if mode == 0o700:
            mode = 0o777
        return _orig_mkdir(path, mode, *args, **kwargs)

    tempfile._os.mkdir = _safe_temp_mkdir
