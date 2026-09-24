import secrets, time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .db import get_db
from .config import get_settings
from .models import User, LoginSession, Area
from .schemas import Register, Login, Preferences, PasswordChange
from .security import current_user, hash_password, verify_password, token_hash, limiter, audit, DUMMY_HASH

router = APIRouter(prefix='/auth', tags=['Authentication'])

def user_view(user):
    return {'id': user.id, 'name': user.name, 'email': user.email, 'roles': user.roles,
            'areas': user.areas, 'preferences': user.preferences, 'active': user.active}

def start_session(db, user, response, request):
    cfg = get_settings()
    old = request.cookies.get(cfg.session_cookie)
    if old:
        item = db.get(LoginSession, token_hash(old))
        if item: db.delete(item)
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=token_hash(token), user_id=user.id, csrf=csrf,
        expires_at=time.time()+cfg.session_hours*3600))
    audit(db, user, 'auth.signin', user.id)
    db.commit()
    response.set_cookie(cfg.session_cookie, token, httponly=True, secure=cfg.cookie_secure,
        samesite='lax', max_age=cfg.session_hours*3600, path='/')
    return {'user': user_view(user), 'csrf_token': csrf}

@router.post('/register', status_code=201)
def register(payload: Register, request: Request, response: Response, db: Session=Depends(get_db)):
    limiter.check('register:'+str(request.client.host), 5, 300)
    user=User(email=str(payload.email).lower(), name=payload.name, password_hash=hash_password(payload.password),
        roles=['reporter'], areas=[], preferences={'followed_areas':[], 'in_app':True, 'sms_opt_in':False, 'language':'en'})
    db.add(user)
    try: db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, 'Registration could not be completed. Try signing in.')
    return start_session(db,user,response,request)

@router.post('/login')
def login(payload: Login, request: Request, response: Response, db: Session=Depends(get_db)):
    limiter.check('login-ip:'+str(request.client.host),20,300)
    limiter.check('login-account:'+str(payload.email).lower(),10,300)
    user=db.query(User).filter(User.email==str(payload.email).lower()).first()
    ok=verify_password(payload.password, user.password_hash if user else DUMMY_HASH)
    if not user or not user.active or not ok: raise HTTPException(401, 'Email or password is incorrect.')
    return start_session(db,user,response,request)

@router.get('/me')
def me(request: Request, user: User=Depends(current_user)):
    return {'user': user_view(user), 'csrf_token': request.state.session.csrf}

@router.post('/logout', status_code=204)
def logout(request: Request, response: Response, user: User=Depends(current_user), db: Session=Depends(get_db)):
    db.delete(request.state.session); audit(db,user,'auth.signout'); db.commit()
    response.delete_cookie(get_settings().session_cookie, path='/')

@router.put('/preferences')
def preferences(payload: Preferences, user: User=Depends(current_user), db: Session=Depends(get_db)):
    available={a.id for a in db.query(Area).all()}
    if not set(payload.followed_areas).issubset(available): raise HTTPException(422,'Unknown community.')
    user.name=payload.name
    user.preferences=payload.model_dump(exclude={'name'})
    audit(db,user,'profile.updated',user.id); db.commit()
    return user_view(user)

@router.post('/password', status_code=204)
def password(payload: PasswordChange, request: Request, response: Response,
             user: User=Depends(current_user), db: Session=Depends(get_db)):
    if not verify_password(payload.current_password,user.password_hash): raise HTTPException(400,'Current password is incorrect.')
    user.password_hash=hash_password(payload.new_password)
    db.query(LoginSession).filter(LoginSession.user_id==user.id).delete(synchronize_session=False)
    audit(db,user,'auth.password_changed',user.id); db.commit()
    response.delete_cookie(get_settings().session_cookie,path='/')
