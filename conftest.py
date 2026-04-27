import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_ignore_collect(collection_path, config):
    path = str(collection_path)
    if "pytest-cache-files-" in path:
        return True
    if path.endswith("tmp\\pytest") or "\\tmp\\pytest\\" in path or path.endswith("tmp/pytest") or "/tmp/pytest/" in path:
        return True
    if path.endswith("youtube_clipper_test.py") and importlib.util.find_spec("googleapiclient") is None:
        return True
    if path.endswith("test_editor_normalization.py") and importlib.util.find_spec("shotstack_sdk") is None:
        return True
    return False


def pytest_collection_modifyitems(config, items):
    has_googleapiclient = importlib.util.find_spec("googleapiclient") is not None
    has_shotstack = importlib.util.find_spec("shotstack_sdk") is not None
    youtube_skip = pytest.mark.skip(reason="googleapiclient is not installed in this test environment")
    shotstack_skip = pytest.mark.skip(reason="shotstack_sdk is not installed in this test environment")
    for item in items:
        path = str(item.fspath)
        if "youtube_clipper_test.py" in path and not has_googleapiclient:
            item.add_marker(youtube_skip)
        if "test_editor_normalization.py" in path and not has_shotstack:
            item.add_marker(shotstack_skip)
