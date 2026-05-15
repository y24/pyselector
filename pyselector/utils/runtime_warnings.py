from __future__ import annotations

import warnings


def configure_runtime_warnings() -> None:
    warnings.filterwarnings(
        "ignore",
        message=r"Revert to STA COM threading mode",
        category=UserWarning,
        module=r"pywinauto",
    )
