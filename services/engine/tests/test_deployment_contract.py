from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def test_render_and_container_preserve_shadow_and_temporary_storage():
    service = yaml.safe_load((ROOT / 'render.yaml').read_text())['services'][0]
    env = {row['key']: row.get('value') for row in service['envVars']}
    assert env['DANTEX_MODE'] == 'shadow'
    assert env['DANTEX_VALIDATION_DURABLE'] == 'false'
    assert env['DANTEX_VALIDATION_DB'].startswith('/tmp/')
    assert service['healthCheckPath'] == '/health'
    assert (ROOT / service['dockerfilePath']).exists()
    assert 'dantex.api:app' in (ROOT / 'Dockerfile').read_text()
    for key in ('UPSTOX_ANALYTICS_TOKEN', 'DANTEX_VALIDATION_REST_KEY'):
        row = next(row for row in service['envVars'] if row['key'] == key)
        assert row['sync'] is False
        assert not row.get('value')
