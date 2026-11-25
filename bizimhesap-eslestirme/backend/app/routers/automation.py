from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.session import get_db
from app import models as m
from app.automation import scheduler as sch

router = APIRouter(prefix="/automation", tags=["Otomasyon"])

class SettingsIn(BaseModel):
    enabled: bool
    interval_minutes: int = Field(ge=1, le=1440)
    min_score: int = Field(ge=0, le=100)
    auto_approve: bool
    date_tolerance_days: int = Field(ge=0, le=365)
    w_amount: int = Field(ge=0, le=100); w_name: int = Field(ge=0, le=100)
    w_invoice_no: int = Field(ge=0, le=100); w_date: int = Field(ge=0, le=100)
    @model_validator(mode="after")
    def _w(self):
        if self.w_amount + self.w_name + self.w_invoice_no + self.w_date <= 0:
            raise ValueError("Ağırlıkların toplamı sıfırdan büyük olmalı.")
        return self

def _get(db):
    s = db.query(m.AutomationSettings).first()
    if not s: s = m.AutomationSettings(); db.add(s); db.commit()
    return s

@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    s = _get(db)
    last = db.query(m.AutomationLog).order_by(m.AutomationLog.id.desc()).first()
    ok, fail = db.query(func.coalesce(func.sum(m.AutomationLog.success_count), 0),
                        func.coalesce(func.sum(m.AutomationLog.fail_count), 0)).one()
    return {**{c: getattr(s, c) for c in SettingsIn.model_fields}, "last_run_at": last.started_at.isoformat() if last else None,
            "next_run_at": sch.next_run_time(), "total_success": ok, "total_fail": fail,
            "note": "Eşleşme skoru istatistiksel olasılık değil, kural tabanlı uygunluk puanıdır."}

@router.put("/settings")
def put_settings(body: SettingsIn, db: Session = Depends(get_db)):
    s = _get(db)
    for k, v in body.model_dump().items(): setattr(s, k, v)
    db.add(m.AuditLog(action="SETTINGS", entity="automation", entity_id=s.id, detail=str(body.model_dump())))
    db.commit(); sch.apply_settings(s.enabled, s.interval_minutes)
    return get_settings(db)

@router.get("/logs")
def logs(db: Session = Depends(get_db)):
    return [{"id": l.id, "started_at": l.started_at.isoformat(), "trigger": l.trigger, "success": l.success_count,
             "fail": l.fail_count, "message": l.message} for l in db.query(m.AutomationLog).order_by(m.AutomationLog.id.desc()).limit(200)]
