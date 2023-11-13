from __future__ import annotations


class ChemtrailsError(Exception):
    pass


class ArchiveError(ChemtrailsError):
    pass


class ArchiveBadFileError(ArchiveError, IOError):
    def __init__(self, filename: str) -> None:
        super().__init__(f"Bad file: {filename}")


class ArchiveUnsupportedVersionError(ArchiveError, ValueError):
    def __init__(self, version: int) -> None:
        super().__init__(f"Unsupported version {version}")


class ArchiveClassMismatchError(ArchiveError, ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unexpected class name {name}")


class ArchiveWrongObjectError(ArchiveError, ValueError):
    def __init__(self, expected: type, got: type) -> None:
        super().__init__(
            f"Expected {expected.__name__} class, found {got.__name__}"
        )
