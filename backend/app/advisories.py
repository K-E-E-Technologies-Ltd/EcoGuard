from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Area, Advisory, Report, Review, Outbox, Receipt, now
from .schemas import AdvisoryWrite, PublishWrite, RetractWrite
from .security import current_user, require_role, require_area, report_access, check_version, audit

router=APIRouter(prefix='/advisories',tags=['Reviewed advisories'])

def advisory_view(db,a,staff=False):
    area=db.get(Area,a.area_id)
    result={k:getattr(a,k) for k in ['id','area_id','category','title','body','source','state','expires_at','published_at','created_at','retraction_reason']}
    result.update(area_name=area.name,latitude=area.latitude,longitude=area.longitude,location_precision='community-centroid')
    if staff:result.update(report_id=a.report_id,version=a.version)
    return result

def editorial_access(db,user,advisory_id,lock=False):
    require_role(user,'publisher')
    q=db.query(Advisory).filter_by(id=advisory_id)
    if lock:q=q.with_for_update()
    a=q.first()
    if not a or a.area_id not in user.areas:raise HTTPException(404,'Advisory not found.')
    return a

@router.get('')
def list_advisories(staff:bool=False,category:str|None=None,area_id:str|None=None,
    user:User=Depends(current_user),db:Session=Depends(get_db)):
    q=db.query(Advisory)
    if staff:
        require_role(user,'publisher','reviewer','responder')
        q=q.filter(Advisory.area_id.in_(user.areas))
    else:
        q=q.filter(Advisory.state=='published',Advisory.expires_at>now())
    if category:q=q.filter(Advisory.category==category)
    if area_id:q=q.filter(Advisory.area_id==area_id)
    items=q.order_by(Advisory.created_at.desc()).limit(200).all()
    read={r.advisory_id for r in db.query(Receipt).filter_by(user_id=user.id).all()}
    return {'items':[dict(advisory_view(db,a,staff),read=a.id in read) for a in items]}

@router.post('',status_code=201)
def create(payload:AdvisoryWrite,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_role(user,'publisher');r=report_access(db,user,payload.report_id);require_area(user,r.area_id)
    # Explicit human verified decision; a prediction can never satisfy this condition.
    verified=db.query(Review).filter_by(report_id=r.id,decision='verified').first()
    if r.state not in ('verified','closed') or not verified:raise HTTPException(409,'A human-verified report is required.')
    a=Advisory(report_id=r.id,area_id=r.area_id,author_id=user.id,category=r.category,
        title=payload.title,body=payload.body,source=payload.source,expires_at=payload.expires_at.isoformat())
    db.add(a);db.flush();audit(db,user,'advisory.draft_created',a.id);db.commit()
    return advisory_view(db,a,True)

@router.get('/{advisory_id}')
def get_advisory(advisory_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    a=db.get(Advisory,advisory_id)
    if not a:raise HTTPException(404,'Advisory not found.')
    staff=bool(set(user.roles).intersection({'reviewer','publisher','responder'})) and a.area_id in user.areas
    if not staff and (a.state not in ('published','retracted') or (a.state=='published' and a.expires_at<=now())):
        raise HTTPException(404,'Advisory is unavailable or expired.')
    return advisory_view(db,a,staff)

@router.post('/{advisory_id}/publish')
def publish(advisory_id:str,payload:PublishWrite,user:User=Depends(current_user),db:Session=Depends(get_db)):
    a=editorial_access(db,user,advisory_id,True);check_version(a,payload.version)
    if a.state!='draft':raise HTTPException(409,'Only drafts can be published.')
    if not payload.privacy_checked or not payload.evidence_checked:raise HTTPException(422,'Complete the evidence and privacy checks.')
    r=db.get(Report,a.report_id)
    if r.state not in ('verified','closed'):raise HTTPException(409,'Source report is no longer verified.')
    if a.expires_at<=now():raise HTTPException(422,'This draft has expired. Create a new advisory.')
    a.state='published';a.publisher_id=user.id;a.published_at=now()
    db.add(Outbox(kind='advisory',aggregate_id=a.id,dedupe_key='advisory:'+a.id))
    audit(db,user,'advisory.published',a.id);db.commit()
    from .jobs import dispatch_pending
    dispatch_pending()
    return advisory_view(db,a,True)

@router.post('/{advisory_id}/retract')
def retract(advisory_id:str,payload:RetractWrite,user:User=Depends(current_user),db:Session=Depends(get_db)):
    a=editorial_access(db,user,advisory_id,True);check_version(a,payload.version)
    if a.state!='published':raise HTTPException(409,'Only published advisories can be retracted.')
    a.state='retracted';a.retraction_reason=payload.reason;audit(db,user,'advisory.retracted',a.id);db.commit()
    return advisory_view(db,a,True)

@router.post('/{advisory_id}/read',status_code=204)
def mark_read(advisory_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    a=db.get(Advisory,advisory_id)
    if not a or a.state not in ('published','retracted'):raise HTTPException(404,'Advisory not found.')
    if not db.query(Receipt).filter_by(user_id=user.id,advisory_id=a.id).first():
        db.add(Receipt(user_id=user.id,advisory_id=a.id));db.commit()
