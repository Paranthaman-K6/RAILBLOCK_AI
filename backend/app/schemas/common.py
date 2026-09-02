from pydantic import BaseModel
from typing import Optional, List, Any

class ErrorDetail(BaseModel):
    row: int
    field: str
    severity: str
    code: str
    message: str

class ImportResult(BaseModel):
    import_run_id: str
    source_name: str
    received_count: int
    accepted_count: int
    rejected_count: int
    warning_count: int
    errors: List[ErrorDetail] = []
    warnings: List[ErrorDetail] = []
    duplicate_count: int
    started_at: str
    completed_at: str
