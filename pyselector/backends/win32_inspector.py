from __future__ import annotations

from pyselector.backends.base import BackendInspector
from pyselector.backends.common import PywinautoInspectorMixin


class Win32Inspector(PywinautoInspectorMixin, BackendInspector):
    backend_name = "win32"
