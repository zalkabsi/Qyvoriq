"""Exercise the real HTTP service and write evidence without secrets."""
from __future__ import annotations

import argparse
import json
import os
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
CALIBRATION = {'minimum_value': 0, 'maximum_value': 100, 'units': 'psi', 'start_angle_deg': 135, 'end_angle_deg': 45, 'sweep_direction': 'clockwise'}


def check_service(url: str, token: str = '') -> dict:
    context = ssl.create_default_context()
    if os.getenv('CODEX_PROXY_CERT'):
        context.load_verify_locations(cafile=os.environ['CODEX_PROXY_CERT'])

    def request(path, body=None, content_type=None, authorized=True):
        headers = {'Authorization': f'Bearer {token}'} if token and authorized else {}
        if content_type:
            headers['Content-Type'] = content_type
        req = urllib.request.Request(url.rstrip('/') + path, data=body, headers=headers)
        try:
            response = urllib.request.urlopen(req, context=context, timeout=45)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            data = response.read()
            return response.status, data

    def upload(path, scenario, initial=True):
        boundary = 'qyvoriq-' + uuid4().hex
        content = bytearray()
        if initial:
            content.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="calibration"\r\n\r\n{json.dumps(CALIBRATION)}\r\n'.encode())
        content.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{scenario}.png"\r\nContent-Type: image/png\r\n\r\n'.encode())
        content.extend((ROOT / 'frontend/public/scenarios' / f'{scenario}.png').read_bytes())
        content.extend(f'\r\n--{boundary}--\r\n'.encode())
        status, raw = request(path, bytes(content), f'multipart/form-data; boundary={boundary}')
        assert status in (200, 201), f'{scenario} HTTP {status}'
        return json.loads(raw)

    status, raw = request('/api/health/ready')
    health = json.loads(raw)
    assert status == 200 and health['opencv_major'] == '5', 'OpenCV 5 readiness failed'
    assert request('/')[0] == 200, 'Frontend page failed'
    if token:
        assert request('/api/benchmarks', authorized=False)[0] == 401, 'Token protection failed'
        assert request('/openapi.json')[0] == 404, 'Production schema should be disabled'
    clear = upload('/api/inspections', 'clear')
    assert clear['state'] == 'VERIFIED' and abs(clear['reading_value'] - 63) <= 2, 'Clear fixture failed'
    glare = upload('/api/inspections', 'glare')
    assert glare['state'] == 'REINSPECTION_REQUIRED', 'Glare did not request a new observation'
    assert not any(event['tool'].startswith('estimate_needle_') for event in glare['trace']), 'Quality gate did not skip estimators'
    continued = upload(f"/api/inspections/{glare['inspection_id']}/images", 'clear', initial=False)
    assert continued['state'] == 'VERIFIED' and continued['attempt_number'] == 2, 'Follow-up failed'
    status, png = request(continued['evidence_url'])
    assert status == 200 and png.startswith(b'\x89PNG\r\n\x1a\n'), 'Evidence PNG failed'
    contradictory = upload('/api/inspections', 'contradictory')
    assert contradictory['state'] == 'REINSPECTION_REQUIRED', 'Ambiguity did not abstain'
    unsupported = upload('/api/inspections', 'unsupported')
    assert unsupported['state'] == 'UNSUPPORTED_INSTRUMENT', 'Unsupported fixture failed'
    status, raw = request('/api/benchmarks')
    benchmark = json.loads(raw)
    assert status == 200 and benchmark['samples'] == 120, 'Benchmark artifact failed'
    return {
        'status': 'passed', 'url': url, 'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'health': health, 'auth_enforced': bool(token),
        'scenario_states': {'clear': clear['state'], 'glare': glare['state'], 'follow_up': continued['state'], 'contradictory': contradictory['state'], 'unsupported': unsupported['state']},
        'evidence_png_bytes': len(png), 'benchmark_samples': benchmark['samples'],
        'data_scope': 'generated synthetic fixtures; not field validation',
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    for name in ('region', 'image-uri', 'image-digest', 'revision', 'service-arn'):
        parser.add_argument('--' + name, default='')
    args = parser.parse_args()
    result = check_service(args.url, os.getenv('QYVORIQ_API_TOKEN', ''))
    result.update({key: getattr(args, key) for key in ('region', 'image_uri', 'image_digest', 'revision', 'service_arn')})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
