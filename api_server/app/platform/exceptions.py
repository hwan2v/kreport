from fastapi import HTTPException
from fastapi import status


class DomainError(Exception):
    """도메인/유즈케이스 공통 베이스 예외"""
    pass

class ResourceNotFound(DomainError):
    def __init__(self, resource: str, detail: str | None = None):
        super().__init__(detail or f"{resource} not found")
        self.resource = resource

class PermissionDenied(DomainError):
    def __init__(self, resource: str, detail: str | None = None):
        super().__init__(detail or f"{resource} permission denied")
        self.resource = resource

class InvalidInput(DomainError):
    def __init__(self, message: str):
        super().__init__(message)

class IndexingFailed(DomainError):
    def __init__(self, index_name: str, reason: str):
        super().__init__(f"Indexing failed for {index_name}: {reason}")
        self.index_name = index_name
