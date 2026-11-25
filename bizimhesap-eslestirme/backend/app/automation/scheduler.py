import os
from apscheduler.schedulers.background import BackgroundScheduler
from app.database.session import SessionLocal
from app import models as m
from app.services import reconciliation_service as svc
from app.services.errors import BusinessError

JOB_ID = "auto_match"
scheduler = BackgroundScheduler(timezone="UTC")

def scheduled_run():
    db = SessionLocal()
    try:
        s = db.query(m.AutomationSettings).first()
        if s and s.enabled: svc.run(db, "scheduled")
    except BusinessError:
        pass   # önceki çalışma sürüyor: aynı anda ikinci çalışma engellendi
    finally:
        db.close()

def apply_settings(enabled: bool, minutes: int):
    if scheduler.running and scheduler.get_job(JOB_ID): scheduler.remove_job(JOB_ID)
    if enabled and scheduler.running:
        # max_instances=1 + coalesce: üst üste binen veya kaçan çalışmalar tek çalışmaya indirilir
        scheduler.add_job(scheduled_run, "interval", minutes=minutes, id=JOB_ID, max_instances=1, coalesce=True)

def next_run_time():
    j = scheduler.get_job(JOB_ID) if scheduler.running else None
    return j.next_run_time.isoformat() if j and j.next_run_time else None

def start():
    if os.getenv("DISABLE_SCHEDULER") == "1": return
    db = SessionLocal()
    try:
        s = db.query(m.AutomationSettings).first()
        if not s: s = m.AutomationSettings(); db.add(s); db.commit()
        if not scheduler.running: scheduler.start()
        apply_settings(s.enabled, s.interval_minutes)
    finally:
        db.close()

def stop():
    if scheduler.running: scheduler.shutdown(wait=False)
