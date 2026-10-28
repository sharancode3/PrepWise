import json
from pathlib import Path
from uuid import uuid4
import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, update
from app.core.config import Settings, BACKEND_ROOT
from app.core.errors import AppError
from app.contracts.domain import GoalCreate, PlanSnapshot
from app.db.models import Base
from app.db.session import Database
from app.features.curriculum.service import seed_curriculum
from app.jobs.runner import JobRunner
from app.main import create_app
from app.providers.gateway import OllamaGateway


@pytest.fixture
def foundation(tmp_path):
    db=Database('sqlite:///'+(tmp_path/'test.db').as_posix())
    config=Config(str(BACKEND_ROOT/'alembic.ini'))
    with db.engine.begin() as connection:
        config.attributes['connection']=connection
        command.upgrade(config,'head')
    with db.sessions.begin() as session:
        seed_curriculum(session)
    settings=Settings(_env_file=None, database_url='sqlite:///'+(tmp_path/'test.db').as_posix(), reasoning_model='',embedding_model='')
    with TestClient(create_app(settings, database=db)) as client:
        yield client,db
    db.engine.dispose()


def identity(client):
    response=client.post('/api/v1/students',json={'display_name':'Test learner'})
    assert response.status_code==201,response.text
    data=response.json()
    return {'X-Local-Token':data['client_token'],'Idempotency-Key':str(uuid4())},data


def goal():
    return json.loads((BACKEND_ROOT.parent/'docs/contracts/goal-create.json').read_text())


def test_migration_seed_health_and_schema(foundation):
    client,db=foundation
    assert client.get('/api/v1/health').status_code==200
    assert set(Base.metadata.tables)==set(inspect(db.engine).get_table_names())-{'alembic_version'}
    with db.sessions.begin() as session:
        assert seed_curriculum(session)['created'] is False
        assert session.execute(select(Base.metadata.tables['questions'].c.reviewed)).scalars().all()==[0]*18
        assert session.connection().exec_driver_sql('PRAGMA foreign_keys').scalar()==1
    assert '/api/v1/goals' in client.get('/openapi.json').json()['paths']


def test_identity_saved_goal_idempotency_and_ownership(foundation):
    client,db=foundation
    headers,student=identity(client)
    assert 'client_token_hash' not in str(client.get('/api/v1/me',headers=headers).json())
    first=client.post('/api/v1/goals',headers=headers,json=goal())
    assert first.status_code==201,first.text
    repeated=client.post('/api/v1/goals',headers=headers,json=goal())
    assert repeated.json()==first.json()
    assert client.get('/api/v1/me',headers=headers).json()['input_revision']==1
    changed=goal();changed['title']='Changed'
    assert client.post('/api/v1/goals',headers=headers,json=changed).json()['error']['code']=='IDEMPOTENCY_CONFLICT'
    other,_=identity(client)
    assert client.get('/api/v1/goals/'+first.json()['goal_id'],headers=other).status_code==404
    assert client.get('/api/v1/me').status_code==401
    with db.sessions() as session:
        stored=session.execute(select(Base.metadata.tables['students'].c.client_token_hash).where(Base.metadata.tables['students'].c.id==student['student_id'])).scalar_one()
        assert stored!=student['client_token']


def test_validation_and_stale_revision(foundation):
    client,_=foundation
    headers,_=identity(client)
    bad=goal();bad['availability'][0]['minutes']=-1
    assert client.post('/api/v1/goals',headers=headers,json=bad).status_code==422
    assert client.get('/api/v1/me',headers=headers).json()['input_revision']==0
    good=client.post('/api/v1/goals',headers=headers,json=goal()).json()
    headers['Idempotency-Key']=str(uuid4())
    stale=client.post('/api/v1/goals',headers=headers,json=goal())
    assert stale.status_code==409
    update_result=client.put('/api/v1/goals/'+good['goal_id']+'/availability',headers={**headers,'Idempotency-Key':str(uuid4())},json={'expected_revision':1,'availability':[]})
    assert update_result.status_code==200,update_result.text
    assert all(row['minutes']==0 for row in update_result.json()['availability'])


def test_planning_flow_versions_and_jobs_recover(foundation):
    client,db=foundation
    headers,student=identity(client)
    saved=client.post('/api/v1/goals',headers=headers,json=goal()).json()
    result=client.post('/api/v1/goals/'+saved['goal_id']+'/plan-jobs',headers=headers,json={'expected_revision':1,'mode':'generate'})
    assert result.status_code==202,result.text
    first_plan=result.json()['plan_id']
    current=client.get('/api/v1/goals/'+saved['goal_id']+'/plans/current',headers=headers)
    assert current.status_code==200,current.text
    assert current.json()['plan_id']==first_plan
    assert current.json()['entries']
    availability_update=client.put('/api/v1/goals/'+saved['goal_id']+'/availability',headers={**headers,'Idempotency-Key':str(uuid4())},json={'expected_revision':1,'availability':[]})
    assert availability_update.status_code==200,availability_update.text
    revised=client.post('/api/v1/goals/'+saved['goal_id']+'/plan-jobs',headers=headers,json={'expected_revision':2,'mode':'replan','base_plan_id':first_plan})
    assert revised.status_code==202,revised.text
    plans=client.get('/api/v1/goals/'+saved['goal_id']+'/plans',headers=headers).json()
    assert len(plans)==2
    assert plans[0]['is_active'] is True
    assert client.get('/api/v1/plans/'+first_plan,headers=headers).status_code==200
    other_headers,_=identity(client)
    other_goal=client.post('/api/v1/goals',headers=other_headers,json=goal()).json()
    other_plan=client.post('/api/v1/goals/'+other_goal['goal_id']+'/plan-jobs',headers=other_headers,json={'expected_revision':1,'mode':'generate'})
    assert other_plan.status_code==202,other_plan.text
    table=Base.metadata.tables['jobs']
    with db.sessions.begin() as session:
        session.execute(table.insert().values(id='queued-job',student_id=student['student_id'],goal_id=saved['goal_id'],mode='generate',status='queued',stage='accepted',accepted_revision=1,request_id='test'))
    runner=JobRunner(db)
    runner.run('queued-job',lambda _: (_ for _ in ()).throw(AppError('TEST_FAILURE','test',500)))
    assert client.get('/api/v1/jobs/queued-job',headers=headers).json()['status']=='failed'
    with db.sessions.begin() as session:
        session.execute(update(table).where(table.c.id=='queued-job').values(status='running'))
    assert runner.recover()==1
    assert client.get('/api/v1/jobs/queued-job',headers=headers).json()['status']=='interrupted'


def test_contract_fixtures():
    root=BACKEND_ROOT.parent/'docs/contracts'
    GoalCreate.model_validate_json((root/'goal-create.json').read_text())
    PlanSnapshot.model_validate_json((root/'plan-example.json').read_text())


def test_gateway_structured_output_vectors_and_bad_response():
    def mock(request):
        if request.url.path=='/api/chat':return httpx.Response(200,json={'message':{'content':'{"title":"Example"}'}})
        if request.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':'reason'},{'name':'embed'}]})
        return httpx.Response(200,json={'embeddings':[[1.0,0.0]]})
    gateway=OllamaGateway(Settings(_env_file=None,reasoning_model='reason',embedding_model='embed'),httpx.MockTransport(mock))
    assert gateway.generate([],{'type':'object'})=={'title':'Example'}
    assert gateway.embed(['example'])==[[1.0,0.0]]
    assert gateway.capabilities()['reasoning_available'] is True
    bad=OllamaGateway(Settings(_env_file=None,embedding_model='embed'),httpx.MockTransport(lambda _:httpx.Response(200,json={'embeddings':[[0,0]]})))
    with pytest.raises(AppError):bad.embed(['example'])
