import csv, io, hashlib, json
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .db import get_db
from .models import User, Area, Report, Evidence, Review, CaseEvent, Message, Advisory, now
from .schemas import ReportWrite, ReportUpdate, VersionRequest, ReviewWrite, AssignWrite, CloseWrite, MessageWrite
from .security import current_user, report_access, can_see_report, is_case_staff, require_role, require_area, check_version, audit

router=APIRouter(prefix='/reports',tags=['Reports and cases'])

def visible_query(db,user):
    q=db.query(Report)
    if is_case_staff(user):
        return q.filter(or_(Report.owner_id==user.id,and_(Report.area_id.in_(user.areas),Report.state!='draft')))
    return q.filter(Report.owner_id==user.id)

def report_view(db,r,user,detail=False):
    data={k:getattr(r,k) for k in ['id','code','client_id','category','title','description','species','area_id',
        'observed_at','share_location','consent','state','version','assignee_id','created_at','updated_at']}
    data['is_owner']=r.owner_id==user.id
    area=db.get(Area,r.area_id)
    data['area_name']=area.name if area else r.area_id
    data['latitude']=r.latitude
    data['longitude']=r.longitude
    data['evidence']=[{'id':e.id,'filename':e.filename,'width':e.width,'height':e.height,
        'url':f'/api/v1/evidence/{e.id}/content'} for e in db.query(Evidence).filter_by(report_id=r.id).all()]
    if detail:
        data['timeline']=[{'id':e.id,'action':e.action,'note':e.note,'created_at':e.created_at}
            for e in db.query(CaseEvent).filter_by(report_id=r.id).order_by(CaseEvent.created_at).all()]
        data['reviews']=[{'id':e.id,'decision':e.decision,'notes':e.notes,'species':e.species,'created_at':e.created_at}
            for e in db.query(Review).filter_by(report_id=r.id).order_by(Review.created_at).all()]
    return data

def event(db,r,user,action,note=''):
    db.add(CaseEvent(report_id=r.id,actor_id=user.id,action=action,note=note))
    r.updated_at=now()
    audit(db,user,'report.'+action,r.id)

def check_evidence(db,user,ids,report_id=None):
    items=[]
    for evidence_id in set(ids):
        e=db.get(Evidence,evidence_id)
        if not e or e.owner_id!=user.id or (e.report_id and e.report_id!=report_id):
            raise HTTPException(422,'An evidence attachment is unavailable.')
        items.append(e)
    return items

def payload_dict(payload):
    data=payload.model_dump(exclude={'evidence_ids','version'})
    data['observed_at']=payload.observed_at.isoformat()
    return data

@router.get('')
def list_reports(user:User=Depends(current_user),db:Session=Depends(get_db),
    category:str|None=None,state:str|None=None,area_id:str|None=None,q:str=Query('',max_length=160),
    mine:bool=False,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):
    query=visible_query(db,user)
    if mine:query=query.filter(Report.owner_id==user.id)
    if category:query=query.filter(Report.category==category)
    if state:query=query.filter(Report.state==state)
    if area_id:query=query.filter(Report.area_id==area_id)
    if q:query=query.filter(or_(Report.title.ilike('%'+q+'%'),Report.code.ilike('%'+q+'%')))
    total=query.count()
    rows=query.order_by(Report.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {'items':[report_view(db,r,user) for r in rows],'total':total,'page':page,'page_size':page_size}

@router.get('/export.csv')
def export(user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_role(user,'reviewer','publisher','responder')
    output=io.StringIO(); writer=csv.writer(output)
    writer.writerow(['code','category','title','area','status','created_at','updated_at'])
    def safe(v):
        s=str(v or '')
        return "'"+s if s.lstrip().startswith(('=','+','-','@','\t','\r')) else s
    for r in visible_query(db,user).limit(10000).all():
        writer.writerow([safe(x) for x in [r.code,r.category,r.title,r.area_id,r.state,r.created_at,r.updated_at]])
    audit(db,user,'reports.exported'); db.commit()
    return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="ecoguard-reports.csv"'})

@router.post('',status_code=201)
def create(payload:ReportWrite,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not db.get(Area,payload.area_id):raise HTTPException(422,'Select an existing community.')
    digest=hashlib.sha256(json.dumps(payload.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()
    existing=db.query(Report).filter_by(owner_id=user.id,client_id=payload.client_id).first()
    if existing:
        if existing.request_hash!=digest:raise HTTPException(409,'This draft key has already been used for different content.')
        return report_view(db,existing,user,True)
    attachments=check_evidence(db,user,payload.evidence_ids)
    r=Report(**payload_dict(payload),owner_id=user.id,code='EG-'+payload.category[0].upper()+'-'+uuid4().hex[:8].upper(),request_hash=digest)
    db.add(r)
    try:db.flush()
    except IntegrityError:
        db.rollback();existing=db.query(Report).filter_by(owner_id=user.id,client_id=payload.client_id).first()
        if existing and existing.request_hash==digest:return report_view(db,existing,user,True)
        raise HTTPException(409,'Draft key conflict. Reload and try again.')
    for e in attachments:e.report_id=r.id
    event(db,r,user,'draft','Report saved privately.');db.commit()
    return report_view(db,r,user,True)

@router.get('/{report_id}')
def get_report(report_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    return report_view(db,report_access(db,user,report_id),user,True)

@router.put('/{report_id}')
def update(report_id:str,payload:ReportUpdate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    r=report_access(db,user,report_id,True);check_version(r,payload.version)
    if r.owner_id!=user.id or r.state not in ('draft','needs_evidence'):
        raise HTTPException(409,'Only the reporter may edit a draft or a report needing evidence.')
    if not db.get(Area,payload.area_id):raise HTTPException(422,'Unknown community.')
    attachments=check_evidence(db,user,payload.evidence_ids,r.id)
    for key,value in payload_dict(payload).items():
        if key!='client_id':setattr(r,key,value)
    for e in db.query(Evidence).filter_by(report_id=r.id).all():
        if e.id not in payload.evidence_ids:e.report_id=None
    for e in attachments:e.report_id=r.id
    event(db,r,user,'edited','Reporter updated the evidence.');db.commit()
    return report_view(db,r,user,True)

@router.post('/{report_id}/submit')
def submit(report_id:str,payload:VersionRequest,user:User=Depends(current_user),db:Session=Depends(get_db)):
    r=report_access(db,user,report_id,True)
    if r.owner_id!=user.id:raise HTTPException(403,'Only the reporter can submit this report.')
    # Safe retry after the first successful submission.
    if r.state=='submitted':return report_view(db,r,user,True)
    check_version(r,payload.version)
    if r.state not in ('draft','needs_evidence'):raise HTTPException(409,'This report cannot be submitted in its current state.')
    r.state='submitted';event(db,r,user,'submitted','Queued for human review; not a public advisory.');db.commit()
    return report_view(db,r,user,True)

@router.post('/{report_id}/review')
def review(report_id:str,payload:ReviewWrite,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_role(user,'reviewer');r=report_access(db,user,report_id,True);require_area(user,r.area_id);check_version(r,payload.version)
    if r.owner_id==user.id:raise HTTPException(403,'A different reviewer must assess your own report.')
    if r.state not in ('submitted','under_review','needs_evidence'):
        raise HTTPException(409,'Only an open review can be decided.')
    if r.assignee_id and r.assignee_id!=user.id:raise HTTPException(403,'This case is assigned to a different reviewer.')
    r.state=payload.decision
    if payload.species is not None:r.species=payload.species
    db.add(Review(report_id=r.id,reviewer_id=user.id,decision=payload.decision,notes=payload.notes,species=payload.species))
    event(db,r,user,payload.decision,payload.notes);db.commit()
    return report_view(db,r,user,True)

@router.post('/{report_id}/assign')
def assign(report_id:str,payload:AssignWrite,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_role(user,'reviewer','responder');r=report_access(db,user,report_id,True);require_area(user,r.area_id);check_version(r,payload.version)
    assignee=db.get(User,payload.assignee_id)
    if not assignee or not assignee.active or r.area_id not in assignee.areas or not set(assignee.roles).intersection({'reviewer','responder'}):
        raise HTTPException(422,'Choose an active reviewer or responder assigned to this area.')
    r.assignee_id=assignee.id;event(db,r,user,'assigned','Case assigned for follow-up.');db.commit()
    return report_view(db,r,user,True)

@router.post('/{report_id}/close')
def close(report_id:str,payload:CloseWrite,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_role(user,'responder');r=report_access(db,user,report_id,True);require_area(user,r.area_id);check_version(r,payload.version)
    if r.state not in ('verified','rejected'):raise HTTPException(409,'Verify or reject the report before closing it.')
    r.state='closed';event(db,r,user,'closed',payload.note);db.commit()
    return report_view(db,r,user,True)

@router.get('/{report_id}/messages')
def messages(report_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    report_access(db,user,report_id)
    return {'items':[{'id':m.id,'body':m.body,'is_mine':m.sender_id==user.id,'sender_label':'You' if m.sender_id==user.id else 'Case participant',
        'created_at':m.created_at} for m in db.query(Message).filter_by(report_id=report_id).order_by(Message.created_at).all()]}

@router.post('/{report_id}/messages',status_code=201)
def send_message(report_id:str,payload:MessageWrite,user:User=Depends(current_user),db:Session=Depends(get_db)):
    r=report_access(db,user,report_id)
    if r.state=='draft':raise HTTPException(409,'Submit the report before sending a message.')
    msg=Message(report_id=report_id,sender_id=user.id,body=payload.body);db.add(msg);audit(db,user,'message.created',report_id);db.commit()
    return {'id':msg.id,'body':msg.body,'is_mine':True,'sender_label':'You','created_at':msg.created_at}
