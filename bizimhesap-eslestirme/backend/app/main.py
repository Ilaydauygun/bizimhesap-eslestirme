from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.session import Base, engine
from fastapi import Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from fastapi.exceptions import RequestValidationError
from app.routers import accounts, transactions, invoices, dashboard, reconciliation, automation
from app.automation import scheduler as sch
from app.services.errors import BusinessError

Base.metadata.create_all(engine)
@asynccontextmanager
async def lifespan(_):
    sch.start()
    yield
    sch.stop()

app = FastAPI(lifespan=lifespan, title="Bizim Hesap - Banka/Fatura Eşleştirme Modülü (Prototip)", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])
@app.exception_handler(BusinessError)
async def _biz(_: Request, e: BusinessError):
    return JSONResponse(status_code=e.status_code, content={"detail": e.message})

@app.exception_handler(RequestValidationError)
async def _val(_: Request, e: RequestValidationError):
    msgs = [f"{'.'.join(str(x) for x in er['loc'][1:])}: {er['msg']}" for er in e.errors()]
    return JSONResponse(status_code=422, content={"detail": "Geçersiz istek — " + "; ".join(msgs)})

for r in (accounts, transactions, invoices, dashboard, reconciliation, automation):
    app.include_router(r.router, prefix="/api")
