from collections import Counter
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from .db import get_db
from .config import get_settings
from .models import User,Area,Report,Advisory,Audit,Outbox,LoginSession,now
from .schemas import UserCreate,UserAccess
from .security import current_user,require_role,hash_password,audit,is_case_staff
from .reports import visible_query,report_view
from .auth import user_view

router=APIRouter(tags=['Workspace, maps, administration'])

@router.get('/health/live')
def live():return {'status':'ok','service':'EcoGuard API'}

@router.get('/health/ready')
def ready(db:Session=Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status':'ok','database': 'postgresql-postgis' if db.bind.dialect.name=='postgresql' else 'sqlite-local-development'}

@router.get('/config')
def config():
    cfg=get_settings()
    return {'name':'EcoGuard Uganda','demo_enabled':cfg.demo_enabled,'application_only':True,
        'image_assistance':'configured' if cfg.model_path and cfg.model_labels_path else 'not_configured',
        'sms':cfg.sms_provider,'max_upload_mb':cfg.max_upload_mb,'languages':['en']}

@router.get('/areas')
def areas(db:Session=Depends(get_db)):
    return {'items':[{'id':a.id,'name':a.name,'description':a.description,'latitude':a.latitude,
        'longitude':a.longitude,'radius_km':a.radius_km} for a in db.query(Area).order_by(Area.name).all()]}

@router.get('/dashboard')
def dashboard(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=visible_query(db,user).all()
    categories=Counter(r.category for r in rows);states=Counter(r.state for r in rows)
    days=Counter(r.created_at[:10] for r in rows)
    return {'counts':{'wildlife':categories['wildlife'],'wetland':categories['wetland'],'flood':categories['flood'],
        'awaiting_review':sum(states[k] for k in ('submitted','under_review','needs_evidence')),'total':len(rows),
        'verified':states['verified'],'closed':states['closed']},
        'states':dict(states),'categories':dict(categories),
        'activity':[{'date':day,'count':count} for day,count in sorted(days.items())[-30:]],
        'recent':[report_view(db,r,user) for r in sorted(rows,key=lambda r:r.created_at,reverse=True)[:6]],
        'scope':'assigned areas and own reports' if is_case_staff(user) else 'your reports',
        'ai_metrics':None,'note':'Operational counts are not field-impact or model-accuracy measurements.'}

@router.get('/map')
def map_data(view:str=Query('community',pattern='^(community|staff)$'),category:str|None=None,
    user:User=Depends(current_user),db:Session=Depends(get_db)):
    features=[]
    if view=='staff':
        require_role(user,'reviewer','responder','publisher')
        query=visible_query(db,user)
        if category:query=query.filter(Report.category==category)
        for r in query.limit(1000).all():
            area=db.get(Area,r.area_id)
            private=r.share_location and r.latitude is not None
            lon,lat=(r.longitude,r.latitude) if private else (area.longitude,area.latitude)
            features.append({'type':'Feature','id':r.id,'geometry':{'type':'Point','coordinates':[lon,lat]},
                'properties':{'id':r.id,'code':r.code,'title':r.title,'category':r.category,'state':r.state,
                    'area_name':area.name,'precision':'private-evidence' if private else 'community-centroid','kind':'report'}})
    else:
        # Public output is built only from active, published advisories, not hidden reports.
        query=db.query(Advisory).filter(Advisory.state=='published',Advisory.expires_at>now())
        if category:query=query.filter(Advisory.category==category)
        for a in query.limit(1000).all():
            area=db.get(Area,a.area_id)
            features.append({'type':'Feature','id':a.id,'geometry':{'type':'Point','coordinates':[area.longitude,area.latitude]},
                'properties':{'id':a.id,'title':a.title,'category':a.category,'state':'published',
                    'area_name':area.name,'precision':'community-centroid','kind':'advisory'}})
    return {'type':'FeatureCollection','features':features,'location_policy':'Private positions are never included in community responses.'}

@router.get('/team/directory')
def directory(user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_role(user,'reviewer','responder','publisher','admin')
    return {'items':[{'id':u.id,'name':u.name,'roles':u.roles,'areas':u.areas} for u in db.query(User).filter_by(active=True).all()
        if set(u.areas).intersection(user.areas) and set(u.roles).intersection({'reviewer','responder','publisher'})]}

@router.get('/admin/users')
def users(user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_role(user,'admin')
    return {'items':[user_view(u) for u in db.query(User).order_by(User.created_at).limit(1000).all()]}

@router.post('/admin/users',status_code=201)
def create_user(payload:UserCreate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_role(user,'admin')
    if db.query(User).filter_by(email=str(payload.email).lower()).first():raise HTTPException(409,'An account with this email already exists.')
    check_areas(db,payload.areas)
    u=User(name=payload.name,email=str(payload.email).lower(),password_hash=hash_password(payload.password),
        roles=list(set(payload.roles)),areas=list(set(payload.areas)),preferences={})
    db.add(u);db.flush();audit(db,user,'access.user_created',u.id);db.commit()
    return user_view(u)

def check_areas(db,ids):
    valid={a.id for a in db.query(Area).all()}
    if not set(ids).issubset(valid):raise HTTPException(422,'Unknown assigned area.')

@router.patch('/admin/users/{user_id}')
def access(user_id:str,payload:UserAccess,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_role(user,'admin')
    if user_id==user.id:raise HTTPException(403,'Ask a different administrator to change your own access.')
    u=db.get(User,user_id)
    if not u:raise HTTPException(404,'User not found.')
    check_areas(db,payload.areas)
    u.roles=list(set(payload.roles));u.areas=list(set(payload.areas));u.active=payload.active
    db.query(LoginSession).filter_by(user_id=u.id).delete(synchronize_session=False)
    audit(db,user,'access.updated_sessions_revoked',u.id);db.commit()
    return user_view(u)

@router.get('/admin/audit')
def audit_log(user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_role(user,'admin')
    return {'items':[{'id':a.id,'actor_id':a.actor_id,'action':a.action,'target_id':a.target_id,'created_at':a.created_at}
        for a in db.query(Audit).order_by(Audit.created_at.desc()).limit(300).all()]}

@router.get('/admin/jobs')
def jobs(user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_role(user,'admin')
    return {'items':[{'id':j.id,'kind':j.kind,'state':j.state,'attempts':j.attempts,'last_error':j.last_error,'created_at':j.created_at}
        for j in db.query(Outbox).order_by(Outbox.created_at.desc()).limit(200).all()]}

@router.get('/stakeholders')
def stakeholders():
    return {'items':[
        {'name':'Farmers and nearby residents','role':'Report sightings, receive reviewed advisories','workspace':'Community mobile PWA'},
        {'name':'Wetland-adjacent communities','role':'Report observed changes and follow up','workspace':'Wetland reporting'},
        {'name':'Flood-risk communities','role':'Report water observations and read sourced updates','workspace':'Flood information'},
        {'name':'Community liaison users','role':'Support reporting and accessibility','workspace':'Assisted community reporting'},
        {'name':'UWA / conservation reviewers','role':'Proposed wildlife verification and follow-up','workspace':'Review and cases'},
        {'name':'Environment officers / NGOs','role':'Proposed wetland verification and response coordination','workspace':'Wetlands and cases'},
        {'name':'Disaster-management partners','role':'Proposed flood-source review and publication','workspace':'Flood advisories'},
        {'name':'Student team and academic supervisor','role':'Design, evaluate and oversee coursework','workspace':'Research documentation'},
        {'name':'Administrators, providers and funders','role':'Operate services and support delivery','workspace':'Access, audit and integrations'}],
        'note':'Institutional names describe potential stakeholders, not confirmed partnerships.'}
