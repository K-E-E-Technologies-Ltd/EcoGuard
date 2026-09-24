import io, hashlib, warnings
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Evidence, Prediction, Outbox
from .schemas import PredictionWrite
from .config import get_settings
from .security import current_user, evidence_access, audit
from . import storage

router=APIRouter(tags=['Private evidence and image assistance'])

def evidence_view(e):
    return {'id':e.id,'filename':e.filename,'width':e.width,'height':e.height,'size':e.size,
        'url':f'/api/v1/evidence/{e.id}/content'}

@router.post('/evidence',status_code=201)
async def upload(file:UploadFile=File(...),user:User=Depends(current_user),db:Session=Depends(get_db)):
    cfg=get_settings();limit=cfg.max_upload_mb*1024*1024
    content=bytearray()
    while chunk:=await file.read(65536):
        content.extend(chunk)
        if len(content)>limit:raise HTTPException(413,'Image exceeds the 10 MB upload limit.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            image=Image.open(io.BytesIO(content))
            if image.format not in ('JPEG','PNG','WEBP'):raise ValueError('Unsupported image.')
            if image.width*image.height>20_000_000:raise ValueError('Image exceeds 20 megapixels.')
            image.load();image=ImageOps.exif_transpose(image).convert('RGB')
            image.thumbnail((2400,2400))
            # Re-encode pixels only: no EXIF location, scripts or source metadata.
            out=io.BytesIO();image.save(out,format='JPEG',quality=88)
            data=out.getvalue()
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise HTTPException(422,'Upload a valid JPG, PNG or WebP image no larger than 20 megapixels.')
    key=uuid4().hex+'.jpg';storage.put(key,data)
    e=Evidence(owner_id=user.id,storage_key=key,filename='evidence-'+key[:8]+'.jpg',content_type='image/jpeg',
        size=len(data),checksum=hashlib.sha256(data).hexdigest(),width=image.width,height=image.height)
    try:
        db.add(e);db.flush();audit(db,user,'evidence.uploaded',e.id);db.commit()
    except Exception:
        storage.remove(key);raise
    return evidence_view(e)

@router.get('/evidence/{evidence_id}/content')
def content(evidence_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    e=evidence_access(db,user,evidence_id)
    try:data=storage.get(e.storage_key)
    except Exception:raise HTTPException(503,'Evidence storage is temporarily unavailable.')
    return Response(data,media_type='image/jpeg',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
        'Content-Disposition':f'inline; filename="{e.filename}"'})

@router.post('/predictions',status_code=202)
def request_prediction(payload:PredictionWrite,user:User=Depends(current_user),db:Session=Depends(get_db)):
    e=evidence_access(db,user,payload.evidence_id)
    # Reuse the most recent job for unchanged evidence/model; no fake results.
    existing=db.query(Prediction).filter_by(evidence_id=e.id,model_version=get_settings().model_version).order_by(Prediction.created_at.desc()).first()
    if existing and existing.state not in ('failed',):return prediction_view(existing)
    p=Prediction(evidence_id=e.id,model_version=get_settings().model_version)
    db.add(p);db.flush()
    job=Outbox(kind='prediction',aggregate_id=p.id,dedupe_key='prediction:'+p.id);db.add(job)
    audit(db,user,'prediction.requested',p.id);db.commit()
    from .jobs import dispatch_pending
    dispatch_pending();db.refresh(p)
    return prediction_view(p)

def prediction_view(p):
    return {k:getattr(p,k) for k in ['id','evidence_id','state','species','confidence','boxes','model_version','explanation','created_at']}

@router.get('/predictions/{prediction_id}')
def prediction(prediction_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    p=db.get(Prediction,prediction_id)
    if not p:raise HTTPException(404,'Image-assistance request not found.')
    evidence_access(db,user,p.evidence_id)
    return prediction_view(p)
