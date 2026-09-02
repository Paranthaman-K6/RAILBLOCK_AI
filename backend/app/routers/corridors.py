from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Corridor, Section, Line

router = APIRouter(prefix="/api", tags=["corridors"])

@router.get("/corridors")
def get_corridors(db: Session = Depends(get_db)):
    return [{"corridor_id":c.id,"name":c.name} for c in db.query(Corridor).all()]

@router.get("/assets")
def get_assets(db: Session = Depends(get_db)):
    from app.models import Asset
    return [{"asset_id":a.id,"corridor_id":a.corridor_id,"section_id":a.section_id,"line_id":a.line_id,"asset_type":a.asset_type} for a in db.query(Asset).all()]
