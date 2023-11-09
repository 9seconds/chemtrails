from __future__ import annotations


class ChemtrailsError(Exception):
    pass


class UnsupportedVersionError(ChemtrailsError, ValueError):
    def __init__(self, version: int) -> None:
        super().__init__(f"Unsupported version {version}")


class ClassMismatchError(ChemtrailsError, ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unexpected class name {name}")
