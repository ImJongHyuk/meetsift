"""Timestamped remote audio providers. Credentials exist in memory only."""
import base64
import json
import math
import tempfile
import wave
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def validate_processing(value):
    if not isinstance(value, dict) or set(value) != {'transcription', 'diarization'}:
        raise ValueError('전사·화자 분리 공급자 설정이 올바르지 않습니다.')
    result = {}
    for stage, original in value.items():
        if not isinstance(original, dict) or original.get('provider') not in {'local', 'server', 'openrouter'}:
            raise ValueError('지원하지 않는 음성 공급자입니다.')
        config = {key: original.get(key, '') for key in ('provider', 'baseUrl', 'model', 'apiKey', 'endpoint', 'responseFormat', 'options')}
        if any(not isinstance(item, str) or len(item) > 10000 for item in config.values()):
            raise ValueError('공급자 설정 값이 올바르지 않습니다.')
        if config['provider'] != 'local':
            url = urlsplit(config['baseUrl'])
            if url.scheme not in {'http', 'https'} or not url.netloc or url.username or url.password or url.query or url.fragment:
                raise ValueError('서버 주소 형식이 올바르지 않습니다.')
            if config['provider'] == 'openrouter':
                if config['baseUrl'].rstrip('/') != 'https://openrouter.ai/api/v1':
                    raise ValueError('OpenRouter 공식 API 주소를 사용하세요.')
                if not config['apiKey']:
                    raise ValueError('OpenRouter API 키가 필요합니다.')
            if not config['model']:
                raise ValueError('모델을 입력하세요.')
            config['endpoint'] = config['endpoint'] or '/audio/transcriptions'
            if not config['endpoint'].startswith('/') or config['endpoint'].startswith('//') or any(c in config['endpoint'] for c in '?\\#') or '..' in config['endpoint'].split('/'):
                raise ValueError('API 경로가 올바르지 않습니다.')
            config['responseFormat'] = config['responseFormat'] or 'verbose_json'
            if config['responseFormat'] not in {'verbose_json', 'diarized_json'}:
                raise ValueError('시간 정보가 포함된 응답 형식이 필요합니다.')
            if config['provider'] == 'openrouter' and config['responseFormat'] != 'verbose_json':
                raise ValueError('OpenRouter는 verbose_json을 사용하세요.')
        if config['options']:
            try:
                if not isinstance(json.loads(config['options']), dict):
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError('공급자 옵션은 JSON 객체여야 합니다.') from None
        result[stage] = config
    return result


def public_processing(config):
    return {stage: {key: entry[key] for key in ('provider', 'baseUrl', 'model', 'endpoint', 'responseFormat') if entry.get(key)}
            for stage, entry in config.items()}


def diarization_options(model):
    if model.startswith('microsoft/mai-transcribe-2'):
        return {'azure': {'diarization': {'enabled': True}}}
    if model.startswith('elevenlabs/'):
        return {'elevenlabs': {'diarize': True}}
    if model.startswith('deepgram/'):
        return {'deepgram': {'diarize': True}}
    return {}


def request_audio(config, audio, stage, client=None):
    headers = {'Authorization': 'Bearer ' + config['apiKey']} if config.get('apiKey') else {}
    options = json.loads(config.get('options') or '{}')
    if stage == 'diarization' and config['provider'] == 'openrouter' and not options:
        options = diarization_options(config['model'])
        if not options:
            raise ValueError('이 OpenRouter 화자 모델의 공급자 옵션을 입력하세요. MAI-Transcribe 2 또는 Scribe v2 프리셋을 사용할 수 있습니다.')
    parameters = {'model': config['model'], 'response_format': config.get('responseFormat') or 'verbose_json', 'language': 'ko'}
    address = config['baseUrl'].rstrip('/') + (config.get('endpoint') or '/audio/transcriptions')
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(180, connect=10), follow_redirects=False, trust_env=False)
    try:
        if config['provider'] == 'openrouter':
            payload = {**parameters, 'input_audio': {'data': base64.b64encode(audio.read_bytes()).decode('ascii'), 'format': 'wav'},
                       'timestamp_granularities': ['segment', 'word']}
            if options:
                payload['provider'] = {'options': options}
            response = client.post(address, headers=headers, json=payload)
        else:
            data = {**parameters, 'timestamp_granularities[]': 'word'}
            if parameters['response_format'] == 'diarized_json':
                data.pop('timestamp_granularities[]')
                data['chunking_strategy'] = 'auto'
            if options:
                data['provider'] = json.dumps({'options': options})
            with audio.open('rb') as stream:
                response = client.post(address, headers=headers, data=data, files={'file': ('recording.wav', stream, 'audio/wav')})
        if response.status_code >= 300:
            # Provider errors can echo request bodies or credentials: do not persist them.
            raise RuntimeError(f'{stage} 공급자 요청 실패 (HTTP {response.status_code}). 주소·모델·API 키와 응답 형식을 확인하세요.')
        try:
            result = response.json()
        except ValueError:
            raise ValueError('공급자가 JSON 응답을 반환하지 않았습니다.') from None
        if not isinstance(result, dict):
            raise ValueError('공급자의 JSON 응답은 객체여야 합니다.')
        return result
    except httpx.HTTPError:
        raise RuntimeError('공급자 서버 연결이 끊겼거나 응답 시간이 초과되었습니다.') from None
    finally:
        if owned:
            client.close()


def interval(item, duration):
    try:
        start, end = float(item['start']), float(item['end'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('공급자 응답에 올바른 시작·종료 시간이 없습니다.') from None
    if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= duration + .05 or start >= duration:
        raise ValueError('공급자 응답의 시간 범위가 녹음 길이를 벗어났습니다.')
    return start, min(end, duration)


def normalize_asr(response, duration):
    sources = response.get('segments')
    if not sources and isinstance(response.get('words'), list) and response['words']:
        sources = [{**word, 'text': word.get('word', word.get('text', '')), 'words': [word]} for word in response['words']]
    if not isinstance(sources, list):
        raise ValueError('시간 정보가 없는 전사 결과입니다. verbose_json 및 타임스탬프 지원 모델을 선택하세요.')
    if not sources and response.get('text', '').strip():
        raise ValueError('시간 정보가 없는 전사 결과입니다. verbose_json 및 타임스탬프 지원 모델을 선택하세요.')
    segments = []
    all_words = response.get('words') or []
    for source in sources:
        start, end = interval(source, duration)
        text = source.get('text')
        if not isinstance(text, str):
            raise ValueError('전사 구간에 텍스트가 없습니다.')
        words = source.get('words')
        if words is None:
            words = [word for word in all_words if word.get('start', -1) >= start and word.get('end', duration + 1) <= end + .05]
        normalized = []
        for word in words:
            ws, we = interval(word, duration)
            wt = word.get('word', word.get('text'))
            if not isinstance(wt, str):
                raise ValueError('단어 텍스트가 올바르지 않습니다.')
            normalized.append({'start': ws, 'end': we, 'text': wt if wt[:1].isspace() else ' ' + wt})
        segments.append({'start': start, 'end': end, 'text': text, 'words': normalized})
    return segments


def normalize_turns(response, duration):
    sources = response.get('turns')
    if sources is None:
        words = response.get('words')
        has_speakers = lambda items: items and all(any(item.get(key) is not None for key in ('speaker_id', 'speaker_label', 'speaker')) for item in items)
        sources = words if isinstance(words, list) and has_speakers(words) else response.get('segments')
    if not isinstance(sources, list):
        raise ValueError('화자 구간이 없습니다. 시간과 화자 ID를 반환하는 모델·API를 사용하세요.')
    turns = []
    for source in sources:
        speaker = source.get('speaker_id', source.get('speaker_label', source.get('speaker')))
        if speaker is None:
            raise ValueError('응답에 화자 ID가 없습니다. 화자 분리를 지원하는 모델과 공급자 옵션을 확인하세요.')
        if not isinstance(speaker, (str, int)) or not str(speaker) or len(str(speaker)) > 200:
            raise ValueError('화자 ID가 올바르지 않습니다.')
        start, end = interval(source, duration)
        turns.append({'start': start, 'end': end, 'speaker_id': str(speaker)})
    return turns


def run_remote(config, audio, stage, request=request_audio):
    """Bound requests to 5-minute chunks; never imply speaker identity across cuts."""
    segments, turns, raw_texts, chunks = [], [], [], []
    with wave.open(str(audio)) as source, tempfile.TemporaryDirectory(prefix='meeting-provider-') as temporary:
        rate = source.getframerate()
        total = source.getnframes()
        frames_per_chunk = rate * 300
        count = math.ceil(total / frames_per_chunk)
        for index, frame in enumerate(range(0, total, frames_per_chunk)):
            source.setpos(frame)
            frames = min(frames_per_chunk, total - frame)
            chunk_path = Path(temporary) / 'chunk.wav'
            with wave.open(str(chunk_path), 'wb') as target:
                target.setparams(source.getparams())
                target.writeframes(source.readframes(frames))
            response = request(config, chunk_path, stage)
            offset, duration = frame / rate, frames / rate
            if stage == 'transcription':
                local = normalize_asr(response, duration)
                for segment in local:
                    boundary = (index > 0 and segment['start'] < 2) or (index < count - 1 and segment['end'] > duration - 2)
                    segment.update(start=segment['start'] + offset, end=segment['end'] + offset,
                                   review_flags=['provider_chunk_boundary'] if boundary else [])
                    for word in segment['words']:
                        word['start'] += offset
                        word['end'] += offset
                segments.extend(local)
                raw_texts.append(response.get('text') if isinstance(response.get('text'), str) else ' '.join(s['text'] for s in local))
            else:
                local = normalize_turns(response, duration)
                for turn in local:
                    turn['start'] += offset
                    turn['end'] += offset
                    turn['speaker_id'] = f'remote_c{index:04d}_{turn["speaker_id"]}'
                turns.extend(local)
            chunks.append({'index': index, 'start': offset, 'end': offset + duration})
    if stage == 'transcription':
        return {'segments': segments, 'raw_asr_text': '\n'.join(raw_texts), 'timing_quality': 'estimated_word' if any(s['words'] for s in segments) else 'estimated_segment',
                'model': config['model'], 'provider': config['provider'], 'provider_chunks': chunks}
    return {'turns': turns, 'model': config['model'], 'provider': config['provider'], 'diarization_mode': 'remote_timestamped',
            'provider_chunks': chunks, 'speaker_linking': 'independent_chunk_speakers' if len(chunks) > 1 else 'single_chunk'}
