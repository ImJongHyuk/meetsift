"""Assign word intervals to speaker activity without hiding overlapping speech."""
from collections import defaultdict


def overlap(a, b, c, d):
    return max(0.0, min(b, d) - max(a, c))


def align(asr, turns):
    result = []
    for source in asr['segments']:
        units = source.get('words') or [{'start': source['start'], 'end': source['end'], 'text': source['text']}]
        for word in units:
            start, end = float(word['start']), float(word['end'])
            scores = defaultdict(float)
            active = []
            for turn in turns:
                amount = overlap(start, end, turn['start'], turn['end'])
                if amount > 0:
                    scores[turn['speaker_id']] += amount
                    active.append(turn)
            candidates = sorted(scores, key=lambda speaker: (-scores[speaker], speaker))
            speaker = candidates[0] if candidates else 'unknown'
            simultaneous = any(a['speaker_id'] != b['speaker_id'] and
                               min(end, a['end'], b['end']) > max(start, a['start'], b['start'])
                               for i, a in enumerate(active) for b in active[i + 1:])
            flags = list(source.get('review_flags', []))
            if simultaneous:
                flags.append('overlapping_speech')
            elif len(candidates) > 1:
                flags.append('speaker_boundary')
            if not candidates:
                flags.append('speaker_unknown')
            quality = asr.get('timing_quality', 'estimated_word') if source.get('words') else 'approximate'
            if quality == 'approximate':
                flags.append('approximate_timing')
            if word.get('probability', 1) < .5:
                flags.append('low_confidence')
            text = word.get('text', word.get('word', ''))
            item = dict(start=start, end=end, text=text, speaker_id=speaker,
                        speaker=speaker, speaker_candidates=candidates, overlap=simultaneous,
                        review_flags=flags, timing_quality=quality, words=[dict(word)])
            # Keep speaker transitions and overlap boundaries visible; short rows remain editable.
            previous = result[-1] if result else None
            if (previous and previous['speaker_id'] == speaker and previous['review_flags'] == flags
                    and previous['speaker_candidates'] == candidates and start - previous['end'] < 1
                    and end - previous['start'] <= 15 and quality != 'approximate'):
                previous['text'] += text
                previous['end'] = end
                previous['words'].append(dict(word))
            else:
                result.append(item)
    for i, item in enumerate(result):
        item['id'] = str(i)
        item['text'] = item['text'].strip()
        item['original_text'] = item['text']
    return result


def joint_segments(asr, turns, duration):
    """Keep joint-model text/time/speaker assignments; activity is review evidence only."""
    import math
    result = []
    for i, source in enumerate(asr['segments']):
        start, end = float(source['start']), float(source['end'])
        if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= duration:
            raise ValueError(f'MOSS segment {i} has invalid timestamp [{start}, {end}] for {duration:.3f}s audio')
        raw_speaker = source.get('raw_speaker_id')
        speaker = source.get('speaker_id')
        if not isinstance(speaker, str) or not speaker.startswith('moss_') or not isinstance(raw_speaker, str) or not raw_speaker:
            raise ValueError(f'MOSS segment {i} has an invalid speaker identifier')
        if not isinstance(source['text'], str):
            raise ValueError(f'MOSS segment {i} has invalid text')
        result.append(dict(id=str(i), start=start, end=end, text=source['text'],
                           original_text=source['text'], speaker_id=speaker, speaker=speaker,
                           raw_speaker_id=raw_speaker, speaker_candidates=[speaker],
                           overlap=False, overlap_sources=[], review_flags=list(source.get('review_flags', [])), words=[],
                           timing_quality='estimated_segment',
                           **{k: source[k] for k in ['chunk_index', 'chunk_id', 'local_start', 'local_end'] if k in source}))
    for i, segment in enumerate(result):
        start, end = segment['start'], segment['end']
        if any(i != j and overlap(start, end, other['start'], other['end']) > 0
               for j, other in enumerate(result)):
            segment['overlap_sources'].append('moss_joint_segments')
        active = [t for t in turns if overlap(start, end, t['start'], t['end']) > 0]
        if any(a['speaker_id'] != b['speaker_id'] and
               min(end, a['end'], b['end']) > max(start, a['start'], b['start'])
               for j, a in enumerate(active) for b in active[j + 1:]):
            segment['overlap_sources'].append('nemotron_activity')
        if segment['overlap_sources']:
            segment['overlap'] = True
            segment['review_flags'].append('overlapping_speech')
    return result
