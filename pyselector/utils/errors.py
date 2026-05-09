from __future__ import annotations


EXIT_OK = 0
EXIT_ELEMENT_NOT_FOUND = 1
EXIT_TARGET_WINDOW_NOT_FOUND = 2
EXIT_UIA_FAILED = 3
EXIT_WIN32_FAILED = 4
EXIT_SELECTOR_EVALUATION_FAILED = 5
EXIT_ARGUMENT_ERROR = 10
EXIT_UNEXPECTED = 100
EXIT_INTERRUPTED = 130


class PySelectorError(Exception):
    exit_code = EXIT_UNEXPECTED


class ArgumentError(PySelectorError):
    exit_code = EXIT_ARGUMENT_ERROR


class CursorError(PySelectorError):
    exit_code = EXIT_ELEMENT_NOT_FOUND


class BackendError(PySelectorError):
    exit_code = EXIT_ELEMENT_NOT_FOUND


class ElementNotFoundError(BackendError):
    exit_code = EXIT_ELEMENT_NOT_FOUND


class TargetWindowNotFoundError(BackendError):
    exit_code = EXIT_TARGET_WINDOW_NOT_FOUND


class SelectorEvaluationError(PySelectorError):
    exit_code = EXIT_SELECTOR_EVALUATION_FAILED


class SelectorEvaluationTimeout(SelectorEvaluationError):
    pass
