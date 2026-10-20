"""Bounded, contiguous MOSS inputs and strict validation of joint outputs."""
import math
import re

CHUNK_SECONDS = 300
MAX_NEW_TOKENS = 16384


def frame_ranges(frames, sample_rate):
    if frames <= 0 or sample_rate <= 0:
        raise ValueError('MOSS requires non-empty audio')
    window = CHUNK_SECONDS * sample_rate
    return [(start, min(start + window, frames)) for start in range(0, frames, window)]


def check_completion(generated, parsed):
    if generated.get('generated_tokens', 0) >= MAX_NEW_TOKENS:
        raise RuntimeError('MOSS reached its output token limit; transcription may be incomplete. Use a shorter recording.')
    raw = generated['text'].strip()
    if raw and (not parsed or not re.search(r'\[[0-9]+(?:\.[0-9]+)?\]$', raw)):
        raise RuntimeError('MOSS returned incomplete or unparseable transcript output')
    headers = re.findall(r'\[[0-9]+(?:\.[0-9]+)?\]\s*\[S[0-9]+\]', raw)
    if len(headers) != len(parsed):
        raise RuntimeError('MOSS transcript contains incomplete segments; output was not silently truncated')


def convert_segments(parsed, chunk_index, start_frame, end_frame, sample_rate, multiple, is_last=False):
    offset = start_frame / sample_rate
    duration = (end_frame - start_frame) / sample_rate
    chunk_id = f'c{chunk_index:04d}'
    result = []
    for i, item in enumerate(parsed):
        start, end = float(item.start), float(item.end)
        if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= duration:
            raise ValueError(f'MOSS chunk {chunk_id}, segment {i} has invalid local timestamp [{start}, {end}] for {duration:.3f}s audio')
        if not isinstance(item.speaker, str) or not item.speaker:
            raise ValueError(f'MOSS chunk {chunk_id} has an invalid speaker identifier')
        if not isinstance(item.text, str):
            raise ValueError(f'MOSS chunk {chunk_id} has invalid transcript text')
        prefix = f'moss_{chunk_id}_' if multiple else 'moss_'
        flags = []
        if multiple and ((chunk_index > 0 and start <= 2) or (not is_last and end >= duration - 2)):
            flags.append('chunk_boundary')
        result.append(dict(start=offset + start, end=offset + end, local_start=start, local_end=end,
                           text=item.text, raw_speaker_id=item.speaker, speaker_id=prefix + item.speaker,
                           chunk_index=chunk_index, chunk_id=chunk_id, words=[], review_flags=flags))
    return result
