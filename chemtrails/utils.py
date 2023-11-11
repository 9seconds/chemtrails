from __future__ import annotations

import traceback


def get_source_line(frame_num: int) -> str:
    tback = traceback.extract_stack(limit=frame_num)[0]

    return f"{tback.filename}:{tback.lineno}"


def get_class_fqn(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def get_filesystem_safe_name(text: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in text)
