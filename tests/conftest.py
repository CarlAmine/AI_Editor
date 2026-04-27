import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import pytest


def pytest_collection_modifyitems(config, items):
    has_googleapiclient = importlib.util.find_spec("googleapiclient") is not None
    if has_googleapiclient:
        return
    skip_marker = pytest.mark.skip(reason="googleapiclient is not installed in this test environment")
    for item in items:
        if "youtube_clipper_test.py" in str(item.fspath):
            item.add_marker(skip_marker)


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
