"""Conservative, whole-speaker permutations across independent MOSS chunks.

Activity agreement is a heuristic, not a calibrated identity probability. A
local speaker is never split between targets; uncertain identities stay local.
"""
from collections import defaultdict
from functools import lru_cache
import math

from .alignment import joint_segments


THRESHOLDS = dict(min_overlap_s=0.5, min_coverage=0.5,
                  min_dominance=0.15, min_assignment_margin=0.1,
                  max_speakers_per_chunk=8)


def _union(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _intersection(left, right):
    i = j = 0
    total = 0.0
    while i < len(left) and j < len(right):
        total += max(0.0, min(left[i][1], right[j][1]) - max(left[i][0], right[j][0]))
        if left[i][1] < right[j][1]:
            i += 1
        else:
            j += 1
    return total


def _assignment(scores, forbidden=None):
    """Maximum-weight partial injective assignment; None is a free dummy."""
    @lru_cache(None)
    def solve(row, used):
        if row == len(scores):
            return 0.0, ()
        value, tail = solve(row + 1, used)
        best = value, (None,) + tail
        for col, weight in enumerate(scores[row]):
            if weight <= 0 or used & (1 << col) or forbidden == (row, col):
                continue
            value, tail = solve(row + 1, used | (1 << col))
            candidate = weight + value
            if candidate > best[0] + 1e-9:
                best = candidate, (col,) + tail
        return best
    return solve(0, 0)


def align_longform_joint(asr: dict, turns: list, duration: float) -> tuple[list[dict], dict]:
    """Return preserved MOSS segments plus auditable chunk permutation evidence.

    Uses unioned activity (seconds) and a bounded exact assignment, with no
    sentence-level speaker reassignment or text/timestamp changes. All accepted
    matches must have both local dominance and a unique global assignment.
    """
    segments = joint_segments(asr, turns, duration)
    chunk_keys = {s.get('chunk_id', s.get('chunk_index', 0)) for s in segments}
    if len(asr.get('chunks', [])) <= 1 and len(chunk_keys) <= 1:
        return segments, dict(applied=False, mode='single_chunk_unchanged', chunks=[])

    global_activity = defaultdict(list)
    for turn in turns:
        start, end = float(turn['start']), float(turn['end'])
        speaker = turn['speaker_id']
        if not isinstance(speaker, str) or not speaker or not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise ValueError('Invalid global speaker activity')
        start, end = max(0.0, start), min(duration, end)
        if end > start:
            global_activity[speaker].append((start, end))
    global_activity = {key: _union(value) for key, value in global_activity.items()}

    grouped = defaultdict(lambda: defaultdict(list))
    local_chunks = {}
    for segment in segments:
        chunk = segment.get('chunk_id')
        if chunk is None:
            index = segment.get('chunk_index')
            if index is None:
                raise ValueError('Multi-chunk MOSS segments require chunk_id or chunk_index')
            chunk = f'c{index:04d}'
        local = segment['speaker_id']
        if local in local_chunks and local_chunks[local] != chunk:
            raise ValueError('Multi-chunk MOSS speaker identifiers must be chunk-scoped')
        local_chunks[local] = chunk
        grouped[chunk][local].append((segment['start'], segment['end']))
        segment['local_speaker_id'] = local

    evidence = dict(applied=True, mode='chunkwise_one_to_one_permutation',
                    confidence_kind='activity_agreement_heuristic_not_probability',
                    thresholds=dict(THRESHOLDS), chunks=[], global_labels={})
    decisions = {}
    for chunk, speakers in grouped.items():
        locals_ = list(speakers)
        activities = [_union(speakers[local]) for local in locals_]
        durations = [sum(end - start for start, end in activity) for activity in activities]
        all_globals = sorted(global_activity)
        matrix = [[_intersection(activity, global_activity[g]) for g in all_globals] for activity in activities]
        relevant = [j for j in range(len(all_globals)) if any(row[j] > 0 for row in matrix)]
        globals_ = [all_globals[j] for j in relevant]
        matrix = [[row[j] for j in relevant] for row in matrix]
        capacity = max(len(locals_), len(globals_)) > THRESHOLDS['max_speakers_per_chunk']
        total, assignment = (0.0, (None,) * len(locals_)) if capacity else _assignment(matrix)
        chunk_evidence = dict(chunk_id=chunk, local_speakers=locals_, global_speakers=globals_,
                              activity_s=durations, intersection_s=matrix,
                              objective_s=total, assignments=[])
        for i, local in enumerate(locals_):
            col = assignment[i]
            score = matrix[i][col] if col is not None else 0.0
            coverage = score / durations[i]
            other = max((value for j, value in enumerate(matrix[i]) if j != col), default=0.0)
            dominance = (score - other) / durations[i] if col is not None else 0.0
            gap = max(0.0, total - _assignment(matrix, (i, col))[0]) if col is not None else 0.0
            margin = gap / durations[i]
            if capacity:
                status, reason = 'unsupported', 'speaker_capacity_exceeded'
            elif col is None:
                status, reason = ('ambiguous', 'injective_assignment_conflict') if any(matrix[i]) else ('unsupported', 'no_activity_support')
            elif score < THRESHOLDS['min_overlap_s'] or coverage < THRESHOLDS['min_coverage']:
                status, reason = 'unsupported', 'insufficient_activity_support'
            elif dominance < THRESHOLDS['min_dominance'] or margin < THRESHOLDS['min_assignment_margin']:
                status, reason = 'ambiguous', 'competing_speaker_activity'
            else:
                status, reason = 'mapped', 'unique_supported_permutation'
            decision = dict(local_speaker_id=local, status=status, reason=reason,
                            proposed_global_speaker_id=globals_[col] if col is not None else None,
                            global_speaker_id=globals_[col] if status == 'mapped' else None,
                            overlap_s=score, coverage=coverage, dominance=dominance,
                            assignment_gap_s=gap, assignment_margin=margin,
                            confidence=max(0.0, min(coverage, dominance, margin)))
            decisions[local] = decision
            chunk_evidence['assignments'].append(decision)
        evidence['chunks'].append(chunk_evidence)

    # Naming follows first temporal appearance, independent of input row ordering.
    for _, segment in sorted(enumerate(segments), key=lambda pair: (pair[1]['start'], pair[0])):
        target = decisions[segment['local_speaker_id']]['global_speaker_id']
        if target is not None and target not in evidence['global_labels']:
            evidence['global_labels'][target] = f"moss_S{len(evidence['global_labels']) + 1:02d}"
    for segment in segments:
        decision = decisions[segment['local_speaker_id']]
        segment['speaker_alignment'] = dict(decision)
        target = decision['global_speaker_id']
        if target is None:
            segment['review_flags'].append(f"speaker_alignment_{decision['status']}")
        else:
            segment['speaker_id'] = evidence['global_labels'][target]
            segment['speaker'] = segment['speaker_id']
            segment['speaker_candidates'] = [segment['speaker_id']]
    return segments, evidence
