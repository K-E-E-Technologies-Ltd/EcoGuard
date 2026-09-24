import hashlib, secrets, time, threading
from collections import defaultdict, deque
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from .db import get_db
from .config import get_settings
from .models import User, LoginSession, Report, Evidence, Audit

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash('not-a-login-password-' + secrets.token_hex(16))
def hash_password(password): return hasher.hash(password)
def verify_password(password, stored):
    try: return hasher.verify(stored, password)
    except (VerifyMismatchError, InvalidHashError): return False

def token_hash(token): return hashlib.sha256(token.encode()).hexdigest()
def audit(db, user, action, target=''):
    db.add(Audit(actor_id=user.id if user else None, action=action, target_id=target))

def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(get_settings().session_cookie, '')
    session = db.get(LoginSession, token_hash(token)) if token else None
    if not session or session.expires_at <= time.time():
        raise HTTPException(401, 'Please sign in again.')
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, 'Account is unavailable.')
    if request.method not in ('GET','HEAD','OPTIONS'):
        csrf = request.headers.get('x-csrf-token', '')
        if not csrf or not secrets.compare_digest(csrf, session.csrf):
            raise HTTPException(403, 'CSRF validation failed. Reload and try again.')
    request.state.session = session
    return user

def require_role(user, *roles):
    if not set(user.roles).intersection(roles):
        raise HTTPException(403, 'Your role does not permit this action.')

def require_area(user, area):
    if area not in user.areas:
        raise HTTPException(403, 'This area is not assigned to you.')

def is_case_staff(user):
    return bool(set(user.roles).intersection({'reviewer','publisher','responder'}))

def can_see_report(user, report):
    return report.owner_id == user.id or (is_case_staff(user) and report.area_id in user.areas and report.state != 'draft')

def report_access(db, user, report_id, lock=False):
    q = db.query(Report).filter(Report.id == report_id)
    if lock: q = q.with_for_update()
    report = q.first()
    if not report or not can_see_report(user, report):
        raise HTTPException(404, 'Report not found.')
    return report

def evidence_access(db, user, evidence_id):
    item = db.get(Evidence, evidence_id)
    if not item: raise HTTPException(404, 'Evidence not found.')
    if item.owner_id != user.id:
        if not item.report_id: raise HTTPException(404, 'Evidence not found.')
        report_access(db, user, item.report_id)
    return item

def check_version(obj, version):
    if obj.version != version:
        raise HTTPException(409, 'This record changed. Reload before saving.')

class RateLimiter:
    """Redis in production; bounded process-local fallback for local development."""
    def __init__(self):
        self.memory = defaultdict(deque)
        self.lock = threading.Lock()
        self.redis = None
    def check(self, key, limit=10, period=60):
        cfg = get_settings()
        if cfg.app_env == 'test': return
        if cfg.app_env == 'production':
            try:
                import redis
                if self.redis is None: self.redis = redis.Redis.from_url(cfg.redis_url, socket_timeout=2)
                bucket = int(time.time() // period)
                k = f'ecoguard:rate:{token_hash(key)}:{bucket}'
                count = self.redis.incr(k)
                if count == 1: self.redis.expire(k, period+1)
            except Exception:
                raise HTTPException(503, 'Authentication temporarily unavailable.')
        else:
            with self.lock:
                now = time.time()
                if len(self.memory) > 5000: self.memory.clear()
                q = self.memory[key]
                while q and q[0] < now-period: q.popleft()
                q.append(now); count = len(q)
        if count > limit:
            raise HTTPException(429, 'Too many attempts. Please try again later.', headers={'Retry-After': str(period)})
limiter = RateLimiter()
