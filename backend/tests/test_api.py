from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_and_sheet_count():
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['drawing_count'] == 26


def test_sheet_catalog_is_j01_to_j26():
    response = client.get('/api/sheets')
    assert response.status_code == 200
    payload = response.json()
    assert payload['standard_frame_count'] == 27
    assert [s['sheet_no'] for s in payload['sheets']] == [f'J{i:02d}' for i in range(1, 27)]


def test_j01_metadata():
    response = client.get('/api/sheets/J01')
    assert response.status_code == 200
    payload = response.json()
    assert payload['sheet_no'] == 'J01'
    assert payload['sheet_name'] == '建筑施工图设计说明（一）'
    assert len(payload['bounding_box']) == 4


def test_j01_entities_if_sample_is_present():
    sheet_path = next((Path('data/sheets').glob('J01_*.dxf')), None)
    if not sheet_path:
        return
    response = client.get('/api/sheets/J01/entities?expand_blocks=true&limit=50000')
    assert response.status_code == 200
    payload = response.json()
    assert payload['returned'] >= 647
    assert payload['expanded_blocks'] is True
    assert payload['truncated'] is False


def test_upload_rejects_non_dxf():
    response = client.post('/api/source/upload', files={'file': ('not-a-dxf.txt', b'hello', 'text/plain')})
    assert response.status_code == 415


def test_split_status_contract():
    response = client.get('/api/source/split-status')
    assert response.status_code == 200
    payload = response.json()
    assert payload['state'] in {'idle', 'queued', 'running', 'completed', 'failed'}
    assert isinstance(payload['processed'], int)
    assert isinstance(payload['total'], int)
