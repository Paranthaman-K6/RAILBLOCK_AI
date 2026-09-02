from fastapi import Header, HTTPException
from typing import Optional

VALID_DEPARTMENTS = ["CONTROL_OFFICE","ENGINEERING","S_AND_T","TRACTION","PROJECTS","VIEWER","ADMIN"]
VALID_ROLES = VALID_DEPARTMENTS  # alias prototype

def get_user_context(
    x_department: Optional[str] = Header(None, alias="X-Department"),
    x_role: Optional[str] = Header(None, alias="X-Role"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    # Demo prototype: allow query param override in routers, header is optional
    dept = (x_department or x_role or "VIEWER").upper()
    if dept not in VALID_DEPARTMENTS:
        dept = "VIEWER"
    return {"department": dept, "user_id": x_user_id or "demo_user", "role": dept}
