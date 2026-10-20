from copy import deepcopy

import pytest

from meeting_backend.alignment import joint_segments
from meeting_backend.longform_alignment import align_longform_joint


def segment(chunk, speaker, start, end, text=' 그대로 둔 원문 '):
    return dict(start=start, end=end, text=text, speaker_id=f'moss_c{chunk:04d}_{speaker}',
                raw_speaker_id=speaker, chunk_id=f'c{chunk:04d}', chunk_index=chunk,
                local_start=start - chunk * 10, local_end=end - chunk * 10)


def asr(*segments):
    return dict(segments=list(segments), chunks=[dict(chunk_id='c0000'), dict(chunk_id='c0001')])


def turn(speaker, start, end):
    return dict(speaker_id=speaker, start=start, end=end)


def test_swapped_chunk_permutation_and_preserved_sources():
    source = asr(segment(0, 'S01', 0, 3), segment(0, 'S02', 4, 7),
                 segment(1, 'S01', 10, 13), segment(1, 'S02', 14, 17))
    activity = [turn('nemo_b', 0, 3), turn('nemo_a', 4, 7),
                turn('nemo_a', 10, 13), turn('nemo_b', 14, 17)]
    before = deepcopy((source, activity))
    output, evidence = align_longform_joint(source, activity, 20)
    assert [s['speaker_id'] for s in output] == ['moss_S01', 'moss_S02', 'moss_S02', 'moss_S01']
    assert evidence['global_labels'] == {'nemo_b': 'moss_S01', 'nemo_a': 'moss_S02'}
    for original, result in zip(source['segments'], output):
        for field in ['start', 'end', 'text', 'raw_speaker_id', 'chunk_id', 'chunk_index', 'local_start', 'local_end']:
            assert original[field] == result[field]
        assert result['local_speaker_id'] == original['speaker_id']
        assert result['original_text'] == original['text']
    assert (source, activity) == before


def test_aggregate_whole_speaker_never_reassigns_one_sentence():
    source = asr(segment(0, 'S01', 0, 6), segment(0, 'S01', 7, 8), segment(1, 'S01', 10, 13))
    output, _ = align_longform_joint(source, [turn('a', 0, 6), turn('b', 7, 8), turn('a', 10, 13)], 20)
    assert [s['speaker_id'] for s in output] == ['moss_S01'] * 3


def test_equal_overlap_is_ambiguous_and_retains_both_texts():
    source = asr(segment(0, 'S01', 0, 4, '동일한 말'), segment(0, 'S02', 0, 4, '동일한 말'),
                 segment(1, 'S01', 10, 12))
    output, evidence = align_longform_joint(source, [turn('a', 0, 4), turn('b', 0, 4)], 20)
    assert [s['speaker_id'] for s in output] == [s['speaker_id'] for s in source['segments']]
    assert len(output) == 3 and [s['text'] for s in output[:2]] == ['동일한 말'] * 2
    assert all(s['overlap'] for s in output[:2])
    assert all('speaker_alignment_ambiguous' in s['review_flags'] for s in output[:2])
    assert 'speaker_alignment_unsupported' in output[2]['review_flags']
    assert evidence['global_labels'] == {}


def test_more_local_speakers_than_globals_does_not_merge():
    source = asr(segment(0, 'S01', 0, 4), segment(0, 'S02', 4, 5), segment(1, 'S01', 10, 12))
    output, evidence = align_longform_joint(source, [turn('a', 0, 5), turn('a', 10, 12)], 20)
    assert [s['speaker_id'] for s in output] == ['moss_S01', 'moss_c0000_S02', 'moss_S01']
    assert output[1]['speaker_alignment']['reason'] == 'injective_assignment_conflict'
    assert 'speaker_alignment_ambiguous' in output[1]['review_flags']
    targets = [d['global_speaker_id'] for d in evidence['chunks'][0]['assignments'] if d['status'] == 'mapped']
    assert len(targets) == len(set(targets))


def test_near_tie_injectivity_is_not_identity_evidence():
    source = asr(segment(0, 'S01', 0, 4), segment(0, 'S02', 4, 8), segment(1, 'S01', 10, 12))
    output, _ = align_longform_joint(source, [turn('a', 0, 8)], 20)
    assert all(s['speaker_id'] == original['speaker_id'] for s, original in zip(output, source['segments']))
    assert all('speaker_alignment_ambiguous' in s['review_flags'] for s in output[:2])


def test_union_activity_avoids_duplicate_support_and_canonical_labels_follow_time():
    source = asr(segment(1, 'S01', 10, 14), segment(0, 'S01', 0, 4), segment(0, 'S01', 2, 4))
    output, evidence = align_longform_joint(source, [turn('b', 10, 14), turn('a', 0, 4), turn('a', 0, 4)], 20)
    assert [s['speaker_id'] for s in output] == ['moss_S02', 'moss_S01', 'moss_S01']
    chunk = next(c for c in evidence['chunks'] if c['chunk_id'] == 'c0000')
    assert chunk['activity_s'] == [4] and chunk['intersection_s'] == [[4]]


def test_single_chunk_matches_existing_joint_output():
    source = dict(segments=[segment(0, 'S01', 0, 3)], chunks=[dict(chunk_id='c0000')])
    source['segments'][0]['speaker_id'] = 'moss_S01'
    activity = [turn('a', 0, 3)]
    output, evidence = align_longform_joint(source, activity, 4)
    assert output == joint_segments(source, activity, 4)
    assert evidence['applied'] is False


def test_capacity_is_bounded_and_unsupported_speakers_stay_local():
    source = asr(*(segment(0, f'S{i:02d}', i, i + 1) for i in range(9)), segment(1, 'S01', 10, 12))
    output, evidence = align_longform_joint(source, [turn('a', 0, 12)], 20)
    assert all(s['speaker_id'] == original['speaker_id'] for s, original in zip(output[:9], source['segments'][:9]))
    assert all(d['reason'] == 'speaker_capacity_exceeded' for d in evidence['chunks'][0]['assignments'])


def test_invalid_unscoped_ids_across_chunks_fail_instead_of_merging():
    source = asr(segment(0, 'S01', 0, 3), segment(1, 'S01', 10, 13))
    source['segments'][1]['speaker_id'] = source['segments'][0]['speaker_id']
    with pytest.raises(ValueError, match='chunk-scoped'):
        align_longform_joint(source, [], 20)


def test_existing_boundary_flags_survive_mapping():
    source = asr(segment(0, 'S01', 0, 3), segment(1, 'S01', 10, 13))
    source['segments'][0]['review_flags'] = ['chunk_boundary']
    output, _ = align_longform_joint(source, [turn('a', 0, 3), turn('a', 10, 13)], 20)
    assert 'chunk_boundary' in output[0]['review_flags']
