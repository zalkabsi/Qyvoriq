"""Record real browser interactions, synthesize narration and export a captioned MP4.

A final recording requires independently produced AWS deployment evidence.
Local recordings are visibly marked as previews throughout.
"""
from __future__ import annotations

import argparse
import asyncio
import html
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import time
import urllib.request
from pathlib import Path

import edge_tts
import edge_tts.communicate
import edge_tts.voices
import playwright
from playwright.sync_api import sync_playwright


def duration(path: Path) -> float:
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(path)], text=True).strip())


def export_movie(video: Path, narration: Path, subtitles: Path, final: Path) -> None:
    subtitle_filter = str(subtitles).replace(':', '\\:').replace("'", "\\'")
    cache = final.parent / 'font-cache'
    cache.mkdir(exist_ok=True)
    env = {**os.environ, 'XDG_CACHE_HOME': str(cache)}
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(video), '-i', str(narration), '-vf', f"subtitles='{subtitle_filter}':force_style='FontName=DejaVu Sans,FontSize=12,MarginV=18,Outline=1.5,Shadow=0'", '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '48000', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', str(final)], check=True, env=env)


def card(title: str, subtitle: str, body: str) -> str:
    return f'''<!doctype html><html><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#12282e;color:#ecf5f1;font-family:Arial,sans-serif;padding:90px 100px;line-height:1.5}}
    .brand{{letter-spacing:7px;color:#61c9ab;font-size:22px;font-weight:bold}}h1{{font-size:62px;line-height:1.12;letter-spacing:-2px;margin:65px 0 20px;max-width:1250px}}
    .sub{{font-size:25px;color:#b9d2ca;max-width:1250px}}.body{{font-size:25px;margin-top:45px;max-width:1300px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}}
    .box{{background:#213c42;border:1px solid #486763;border-radius:16px;padding:25px;min-height:150px}}strong{{color:#7bddbc}}small{{font-size:18px;color:#bfd2ca}}code{{font-size:20px;color:#9ce2ca}}p{{margin:12px 0}}
    </style><div class=brand>QYVORIQ / OPENCV 5</div><h1>{html.escape(title)}</h1><div class=sub>{html.escape(subtitle)}</div><div class=body>{body}</div></html>'''


def encoder_cache(output: Path) -> None:
    # Use the installed system encoder without downloading a second executable.
    package = Path(playwright.__file__).parent / 'driver/package/browsers.json'
    revision = next(entry['revision'] for entry in json.loads(package.read_text())['browsers'] if entry['name'] == 'ffmpeg')
    cache = output / 'browser-cache'
    target = cache / f'ffmpeg-{revision}' / 'ffmpeg-linux'
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.symlink_to(shutil.which('ffmpeg'))
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(cache)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--team', required=True, help='Confirmed credit text; no invented team members.')
    parser.add_argument('--voice', default='en-US-EmmaMultilingualNeural')
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--deployment-evidence', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for subdir in ('audio', 'proof', 'raw'):
        (output / subdir).mkdir(exist_ok=True)
    context = ssl.create_default_context()
    if os.getenv('CODEX_PROXY_CERT'):
        context.load_verify_locations(cafile=os.environ['CODEX_PROXY_CERT'])
        for module in (edge_tts.communicate, edge_tts.voices):
            module._SSL_CTX.load_verify_locations(cafile=os.environ['CODEX_PROXY_CERT'])
    token = os.getenv('QYVORIQ_API_TOKEN', '')
    auth = {'Authorization': f'Bearer {token}'} if token else {}

    def api(path):
        req = urllib.request.Request(args.url.rstrip('/') + path, headers=auth)
        with urllib.request.urlopen(req, context=context, timeout=30) as response:
            return json.load(response)

    health, benchmark = api('/api/health/ready'), api('/api/benchmarks')
    assert health['opencv_major'] == '5' and benchmark['available']
    deployment = json.loads(args.deployment_evidence.read_text()) if args.deployment_evidence else {}
    if not args.preview:
        assert deployment.get('status') == 'passed' and deployment.get('auth_enforced'), 'Final recording requires a passing deployed-service smoke check.'
        assert deployment.get('url', '').rstrip('/') == args.url.rstrip('/') and args.url.startswith('https://')
        assert deployment['health']['revision'] == health['revision'] and health['revision'] not in ('unknown', 'development')
    agent = benchmark['summary']['qyvoriq_selective']
    fixed = benchmark['summary']['baseline_b_fixed_mean']
    paired = benchmark['paired_reinspection']
    label = 'LOCAL PREVIEW · AWS DEPLOYMENT PENDING' if args.preview else f"AWS LIVE DEMO · {deployment['region']}"
    intro_status = 'This preview runs locally. The AWS deployment is still pending.' if args.preview else f"This recording uses the live AWS service in {deployment['region']}."
    cloud_text = (
        'The AWS deployment package uses ECS Express Mode, private ECR images, a token in Secrets Manager, and CloudWatch logs. It will run this same OpenCV processing on AWS behind managed HTTPS. Access is still pending in this preview, so a template is not being presented as cloud execution.'
        if args.preview else
        f"The URL shown here is the verified AWS endpoint in {deployment['region']}. ECS Express Mode runs the actual OpenCV workload from an immutable ECR image. Secrets Manager provides the API token, and CloudWatch records operational logs. Readiness reports OpenCV {health['opencv_version']} on {health['architecture']}."
    )
    scenes = [
        ('intro', 18, f"This is Qyvoriq, created by {args.team}. Analog gauges are still common in maintenance and inspection. A photograph can contain glare, blur, or an ambiguous pointer. Qyvoriq reads calibrated dials and asks for more evidence when its checks fail. {intro_status}"),
        ('clear', 29, 'We start with a generated gauge set to sixty-three psi. The operator supplies the scale, units, angle endpoints, and sweep direction. OpenCV measures image quality and locates the circular dial. A geometric line estimator and a polar estimator produce separate candidates. The displayed value is accepted only under the stated quality, geometry, calibration, and agreement policy.'),
        ('glare', 37, 'Now the same generated dial has a glass reflection. The quality check changes what the agent does next: it skips both needle estimators and requests another observation. The decision trace shows those executed actions. We upload the paired clear control image, keeping the same stable gauge setting. The agent measures again and accepts the second observation. This is a controlled synthetic follow-up, not a physical camera retake.'),
        ('limits', 34, 'Two pointers create contradictory evidence. Disagreement selects one contrast-normalized refinement, then another image request. Repeating this ambiguous frame exhausts the two permitted follow-ups and leads to human review. A digital meter is outside the supported scope and produces no reading. The operator can start a separate inspection; calibration stays fixed while continuing an existing one.'),
        ('architecture', 26, 'The browser sends calibration and pixels to FastAPI. OpenCV five handles image quality, circular geometry, needle estimation, contrast refinement, and annotation. A deterministic agent policy selects acceptance, another observation, or human review. Both estimators share geometry, so their errors can be correlated. The system supports calibrated circular single-pointer dials and does not control equipment.'),
        ('evaluation', 37, f"The evaluation tab shows actual results from {benchmark['samples']} held-out synthetic images. Qyvoriq accepted {agent['predicted_count']}, at {agent['coverage'] * 100:.2f} percent coverage and {agent['mae_fs_pct']:.4f} percent full-scale mean absolute error. The fixed-mean baseline accepted {fixed['predicted_count']} with similar error. The policy therefore trades coverage for caution; this test does not prove a real-world accuracy advantage. Separately, all {paired['samples']} controlled glare and clear pairs resolved within two percent of full scale, and persistent glare escalated at the retry limit."),
        ('cloud', 24, cloud_text),
        ('closing', 17, 'The source, pinned dependencies, tests, benchmark artifacts, report, and reproduction instructions are public on GitHub. Qyvoriq demonstrates an observable perception, decision, and action loop with explicit uncertainty. Real photographs and physical retake trials remain future validation work. A verified status means the configured checks passed; a qualified operator remains responsible for the measurement.'),
    ]

    async def synthesize():
        for name, _, text in scenes:
            path = output / 'audio' / f'{name}.mp3'
            fingerprint = hashlib.sha256((args.voice + ':' + text).encode()).hexdigest()
            stamp_path = path.with_suffix('.sha256')
            if not path.exists() or not stamp_path.exists() or stamp_path.read_text() != fingerprint:
                await edge_tts.Communicate(text, voice=args.voice, proxy=os.getenv('HTTPS_PROXY')).save(str(path))
                stamp_path.write_text(fingerprint)
            print(json.dumps({'narration_scene': name, 'audio_seconds': round(duration(path), 2)}), flush=True)

    asyncio.run(synthesize())
    timing = {name: max(minimum, duration(output / 'audio' / f'{name}.mp3') + 1.8) for name, minimum, _ in scenes}
    assert sum(timing.values()) < 292, 'Narration exceeds the five-minute budget.'
    encoder_cache(output)
    checks = []
    markers = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.getenv('QYVORIQ_CHROMIUM') or shutil.which('chromium'), headless=True, args=['--no-sandbox'])
        browser_context = browser.new_context(viewport={'width': 1600, 'height': 1000}, record_video_dir=str(output / 'raw'), record_video_size={'width': 1600, 'height': 1000})
        page = browser_context.new_page()
        recording_start = time.monotonic()

        def badge():
            page.evaluate('''text => { const old=document.querySelector('#demo-label'); if(old)old.remove(); const node=document.createElement('div'); node.id='demo-label'; node.textContent=text+'   |   SYNTHETIC FIXTURES   |   SYNTHETIC NARRATION'; Object.assign(node.style,{position:'fixed',top:'0',left:'0',width:'100%',zIndex:'2147483647',padding:'8px 16px',font:'bold 12px Arial',letterSpacing:'1px',color:'#fff',background:'#12342e',textAlign:'center',pointerEvents:'none'});document.body.appendChild(node); }''', label)

        def app():
            page.goto(args.url, wait_until='networkidle')
            page.evaluate("document.body.style.zoom='1.1'")
            if token:
                page.get_by_role('button', name='Access token', exact=True).click()
                page.get_by_label('API access token').fill(token)
                page.get_by_role('button', name='Apply', exact=True).click()
            badge()

        def sample(name):
            page.get_by_role('button', name=re.compile('^' + re.escape(name))).click()
            page.wait_for_timeout(700)

        def submit(expected):
            with page.expect_response(lambda response: response.request.method == 'POST' and '/api/inspections' in response.url) as response_info:
                page.locator('.primary-button').click()
            response = response_info.value
            result = response.json()
            assert response.ok and result['state'] == expected, f'Browser demo expected {expected}, got {result.get("state")} (HTTP {response.status})'
            page.locator('img[alt^="OpenCV evidence"]').wait_for(state='visible')
            page.wait_for_timeout(1000)
            checks.append({'state': result['state'], 'attempt': result['attempt_number'], 'reading': result['reading_value']})
            return result

        for name, _, narration in scenes:
            started = time.monotonic()
            offset = started - recording_start
            if name == 'intro':
                page.set_content(card('The vision agent that knows when to pause.', args.team + ' · Solo creator', '<p>OpenCV 5 · calibrated analog gauge inspection</p><p><strong>Evidence → decision → next observation</strong></p>'))
                badge()
            elif name == 'clear':
                app()
                sample('Clear gauge')
                page.locator('.form-grid').scroll_into_view_if_needed()
                page.wait_for_timeout(4500)
                submit('VERIFIED')
                page.locator('.evidence-section').scroll_into_view_if_needed()
                page.screenshot(path=str(output / 'proof/clear.png'))
                page.wait_for_timeout(4000)
                page.locator('.trace-section').scroll_into_view_if_needed()
            elif name == 'glare':
                page.get_by_role('button', name='Start a new inspection').click()
                sample('Glass reflection')
                first = submit('REINSPECTION_REQUIRED')
                assert page.locator('.form-grid input').first.is_disabled()
                page.locator('.trace-section').scroll_into_view_if_needed()
                page.screenshot(path=str(output / 'proof/glare.png'))
                page.wait_for_timeout(7000)
                sample('Clear gauge')
                second = submit('VERIFIED')
                assert first['inspection_id'] == second['inspection_id'] and second['attempt_number'] == 2
                page.locator('.evidence-section').scroll_into_view_if_needed()
                page.screenshot(path=str(output / 'proof/follow-up.png'))
            elif name == 'limits':
                page.get_by_role('button', name='Start a new inspection').click()
                sample('Two pointers')
                submit('REINSPECTION_REQUIRED')
                page.locator('.trace-section').scroll_into_view_if_needed()
                page.wait_for_timeout(4000)
                submit('REINSPECTION_REQUIRED')
                submit('HUMAN_REVIEW_REQUIRED')
                page.locator('.decision-card').scroll_into_view_if_needed()
                page.screenshot(path=str(output / 'proof/human-review.png'))
                page.wait_for_timeout(4500)
                page.get_by_role('button', name='Start a new inspection').click()
                sample('Digital meter')
                submit('UNSUPPORTED_INSTRUMENT')
                page.locator('.decision-card').scroll_into_view_if_needed()
                page.screenshot(path=str(output / 'proof/unsupported.png'))
            elif name == 'architecture':
                host = 'AWS ECS Express Mode (planned)' if args.preview else 'AWS ECS Express Mode (live)'
                page.set_content(card('Perception changes the next action.', host, '<div class=grid><div class=box>React workspace<br><small>Calibration + image upload</small></div><div class=box>FastAPI + OpenCV 5<br><small>Quality → geometry → two estimators</small></div><div class=box>Agent policy<br><small>Accept / refine / request / escalate</small></div></div><p><strong>New observation ↺</strong> user remains in control</p><p><small>Shared geometry means estimator errors can be correlated. In-memory evidence is bounded and expires.</small></p>'))
                badge()
            elif name == 'evaluation':
                app()
                page.get_by_role('button', name='Evaluation', exact=True).click()
                page.get_by_text('Qyvoriq selective policy', exact=True).wait_for()
                page.wait_for_timeout(6000)
                page.screenshot(path=str(output / 'proof/evaluation.png'))
                page.get_by_text('Controlled follow-up observations', exact=True).scroll_into_view_if_needed()
                page.wait_for_timeout(6000)
                page.screenshot(path=str(output / 'proof/paired-evaluation.png'))
            elif name == 'cloud':
                if not args.preview:
                    page.goto(args.url.rstrip('/') + '/api/health/ready', wait_until='networkidle')
                    page.wait_for_timeout(4500)
                state = 'AWS access pending' if args.preview else 'Verified AWS processing'
                meta = 'No cloud endpoint is claimed in this preview.' if args.preview else html.escape(args.url) + '<br>' + html.escape(deployment['region']) + ' · ' + html.escape(health['architecture'])
                page.set_content(card(state, 'ECS Express Mode · private ECR · Secrets Manager · CloudWatch', f'<p>{meta}</p><p>Actual readiness: <code>OpenCV {html.escape(health["opencv_version"])}</code></p><p><small>Public source: github.com/zalkabsi/Qyvoriq</small></p>'))
                badge()
            else:
                page.set_content(card('Ask for evidence. Keep human control.', args.team + ' · Qyvoriq', '<p><strong>Reproducible code, measured results, visible limitations.</strong></p><p>github.com/zalkabsi/Qyvoriq</p><p><small>Synthetic-only evaluation · no field validation · no safety-critical guarantee · no COOL claim</small></p>'))
                badge()
            elapsed = time.monotonic() - started
            page.wait_for_timeout(max(0, timing[name] - elapsed) * 1000)
            markers.append({'scene': name, 'start': round(offset, 3), 'duration': round(time.monotonic() - started, 3), 'narration': narration})
            print(json.dumps({'recorded_scene': name, 'duration': markers[-1]['duration']}), flush=True)
        video_path = Path(page.video.path())
        browser_context.close()
        browser.close()
    # Align each narration clip with the measured scene boundary, including pauses.
    segments = []
    subtitle_lines = []
    subtitle_index = 1

    def stamp(seconds):
        millis = round(seconds * 1000)
        hours, millis = divmod(millis, 3_600_000)
        minutes, millis = divmod(millis, 60_000)
        seconds, millis = divmod(millis, 1000)
        return f'{hours:02}:{minutes:02}:{seconds:02},{millis:03}'

    for marker in markers:
        name = marker['scene']
        segment = output / 'audio' / f'{name}.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(output / 'audio' / f'{name}.mp3'), '-af', f'apad,atrim=0:{marker["duration"]}', '-ar', '48000', '-ac', '2', str(segment)], check=True)
        segments.append(segment)
        sentences = re.split(r'(?<=[.!?])\s+', marker['narration'])
        words = sum(len(sentence.split()) for sentence in sentences)
        voice_seconds = duration(output / 'audio' / f'{name}.mp3')
        position = marker['start']
        for sentence in sentences:
            end = position + voice_seconds * len(sentence.split()) / words
            subtitle_lines.extend([str(subtitle_index), f'{stamp(position)} --> {stamp(end)}', sentence, ''])
            position = end
            subtitle_index += 1
    concat = output / 'audio/concat.txt'
    concat.write_text(''.join(f"file '{path.as_posix()}'\n" for path in segments), encoding='utf-8')
    narration_path = output / 'narration.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat), str(narration_path)], check=True)
    subtitles = output / 'captions.srt'
    subtitles.write_text('\n'.join(subtitle_lines), encoding='utf-8')
    final = output / ('qyvoriq-local-preview.mp4' if args.preview else 'qyvoriq-judge-demo.mp4')
    export_movie(video_path, narration_path, subtitles, final)
    seconds = duration(final)
    assert seconds <= 300, 'Export is over the competition time limit.'
    artifact = {'preview': args.preview, 'team': args.team, 'voice': args.voice, 'speech_service': 'speech.platform.bing.com', 'url': args.url, 'health': health, 'duration_seconds': seconds, 'video': str(final), 'scene_timing': markers, 'browser_checks': checks}
    (output / 'recording-evidence.json').write_text(json.dumps(artifact, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'video': str(final), 'preview': args.preview, 'duration_seconds': seconds, 'browser_checks': len(checks)}, indent=2))


if __name__ == '__main__':
    main()
