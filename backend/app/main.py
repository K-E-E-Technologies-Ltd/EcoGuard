from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError
from .config import get_settings
from .db import Base,engine
from . import models,auth,reports,evidence,advisories,workspace

cfg=get_settings()
@asynccontextmanager
async def lifespan(app):
    if cfg.auto_create_tables and cfg.app_env!='production':Base.metadata.create_all(engine)
    yield

app=FastAPI(title='EcoGuard Uganda API',version='1.0.0',
    description='Wildlife-first reporting, private evidence and human-reviewed advisories. Cookie authentication plus X-CSRF-Token for writes.',
    docs_url='/api/docs' if cfg.enable_api_docs else None,
    redoc_url='/api/redoc' if cfg.enable_api_docs else None,
    openapi_url='/api/openapi.json' if cfg.enable_api_docs else None,lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=cfg.origins,allow_credentials=True,
    allow_methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS'],allow_headers=['Content-Type','X-CSRF-Token'],
    expose_headers=['X-Request-ID','Content-Disposition'])

@app.middleware('http')
async def safeguards(request:Request,call_next):
    request_id=str(uuid4())
    origin=request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin and origin.rstrip('/') not in cfg.origins:
        return JSONResponse(status_code=403,content={'detail':'This origin is not allowed.'})
    size=request.headers.get('content-length')
    if size and size.isdigit() and int(size)>(cfg.max_upload_mb+1)*1024*1024:
        return JSONResponse(status_code=413,content={'detail':'Request too large.'})
    response=await call_next(request)
    response.headers['X-Request-ID']=request_id
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Cache-Control']='no-store'
    return response

@app.exception_handler(StaleDataError)
async def conflict(request,exc):
    return JSONResponse(status_code=409,content={'detail':'Another user changed this record. Reload and try again.'})

for router in [auth.router,reports.router,evidence.router,advisories.router,workspace.router]:
    app.include_router(router,prefix='/api/v1')
