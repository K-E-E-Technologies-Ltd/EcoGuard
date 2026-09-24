import os,tempfile
os.environ['DATABASE_URL']='sqlite:///'+os.path.join(tempfile.gettempdir(),'ecoguard_smoke.db')
os.environ['AUTO_CREATE_TABLES']='true'
os.environ['APP_ENV']='development'
os.environ['ALLOWED_ORIGINS']='http://localhost:5173'
os.environ['ENABLE_API_DOCS']='true'
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base,engine
Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
with TestClient(app) as c:
    r=c.post('/api/v1/auth/register',json={'email':'smoke@example.org','name':'Smoke Test','password':'SmokePassword123!'})
    assert r.status_code==201,r.text
    assert c.get('/api/v1/auth/me').status_code==200
    print('EcoGuard API smoke test: PASS')
