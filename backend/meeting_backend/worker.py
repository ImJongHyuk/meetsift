"""One inference stage per process. Exiting releases its GPU allocations."""
import argparse
import json
import os
from pathlib import Path


def asr(args):
    if args.profile == 'moss':
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor
        from moss_transcribe_diarize import parse_transcript
        from moss_transcribe_diarize.inference_utils import build_transcription_messages, generate_transcription
        torch.set_num_threads(4)
        torch.manual_seed(0)
        # The pinned model requires its custom Python implementation.
        processor = AutoProcessor.from_pretrained(args.model, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(args.model, trust_remote_code=True,
                    dtype=torch.float16, attn_implementation='sdpa').to('cuda').eval()
        import tempfile
        import soundfile as sf
        # Workers are launched as scripts as well as imported in tests.
        try:
            from .moss_chunks import CHUNK_SECONDS, MAX_NEW_TOKENS, frame_ranges, check_completion, convert_segments
        except ImportError:
            from moss_chunks import CHUNK_SECONDS, MAX_NEW_TOKENS, frame_ranges, check_completion, convert_segments
        segments, chunks = [], []
        with sf.SoundFile(args.audio) as audio, tempfile.TemporaryDirectory(prefix='meeting-moss-') as temporary:
            if audio.samplerate != 16000 or audio.channels != 1:
                raise ValueError('MOSS expects normalized 16 kHz mono WAV')
            windows = frame_ranges(len(audio), audio.samplerate)
            for index, (start_frame, end_frame) in enumerate(windows):
                audio.seek(start_frame)
                samples = audio.read(end_frame - start_frame, dtype='float32')
                if len(samples) != end_frame - start_frame:
                    raise RuntimeError('Audio ended before the expected chunk boundary')
                chunk_path = Path(temporary) / 'chunk.wav'
                sf.write(chunk_path, samples, audio.samplerate, subtype='PCM_16')
                del samples
                generated = generate_transcription(model, processor, build_transcription_messages(str(chunk_path)),
                            max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                            device=torch.device('cuda'), dtype=torch.float16)
                raw_chunk = dict(chunk_index=index, chunk_id=f'c{index:04d}',
                                 start=start_frame / audio.samplerate, end=end_frame / audio.samplerate,
                                 start_frame=start_frame, end_frame=end_frame, sample_rate=audio.samplerate,
                                 raw_structured_text=generated['text'],
                                 generated_tokens=generated.get('generated_tokens'), prompt_len=generated.get('prompt_len'))
                # Keep the exact generated output even if validation later rejects it.
                raw_path = Path(args.output).with_name(f'{Path(args.output).stem}.chunk{index:04d}.raw.json')
                raw_path.write_text(json.dumps(raw_chunk, ensure_ascii=False, indent=2))
                parsed = parse_transcript(generated['text'])
                check_completion(generated, parsed)
                segments.extend(convert_segments(parsed, index, start_frame, end_frame,
                                                  audio.samplerate, len(windows) > 1, is_last=index == len(windows) - 1))
                chunks.append(raw_chunk)
                print(f'MOSS chunk {index + 1}/{len(windows)} completed', flush=True)
                del generated, parsed
                torch.cuda.empty_cache()
        return dict(segments=segments, chunks=chunks, timing_quality='estimated_segment', joint_diarization=True,
                    raw_asr_text=' '.join(s['text'] for s in segments),
                    raw_structured_text=chunks[0]['raw_structured_text'] if len(chunks) == 1 else None,
                    model='OpenMOSS-Team/MOSS-Transcribe-Diarize', precision='float16',
                    decoding={'do_sample': False, 'max_new_tokens': MAX_NEW_TOKENS, 'attn_implementation': 'sdpa',
                              'chunk_seconds': CHUNK_SECONDS, 'chunk_overlap_seconds': 0},
                    declared_helper_source_revision='e3bdd93f8ad58418e04659818efd5fd87a0bc486')
    if args.profile.startswith('whisper-'):
        from faster_whisper import WhisperModel
        precision = 'int8_float16' if args.profile == 'whisper-int8' else 'float16'
        model = WhisperModel(args.model, device='cuda', compute_type=precision, cpu_threads=4, num_workers=1)
        stream, info = model.transcribe(args.audio, language='ko', beam_size=1, temperature=0,
                                       condition_on_previous_text=False, vad_filter=True, word_timestamps=True)
        segments = [dict(start=s.start, end=s.end, text=s.text,
                         words=[dict(start=w.start, end=w.end, text=w.word, probability=w.probability)
                                for w in (s.words or [])]) for s in stream]
        return dict(segments=segments, timing_quality='estimated_word',
                    raw_asr_text=' '.join(s['text'].strip() for s in segments),
                    model='Systran/faster-whisper-large-v3', precision=precision, vad=True,
                    decoding={'language': 'ko', 'beam_size': 1, 'temperature': 0,
                              'condition_on_previous_text': False, 'vad_filter': True, 'word_timestamps': True})
    import torch
    import soundfile as sf
    from qwen_asr import Qwen3ASRModel
    model = Qwen3ASRModel.from_pretrained(args.model, dtype=torch.float16, device_map='cuda:0',
                                        max_inference_batch_size=1, max_new_tokens=512)
    # Chunk boundaries are approximate playback anchors, never forced-aligned words.
    segments = []
    with sf.SoundFile(args.audio) as audio:
        offset = 0
        while len(samples := audio.read(25 * 16000, dtype='float32')):
            text = model.transcribe(audio=(samples, 16000), language='Korean')[0].text
            end = offset + len(samples) / 16000
            if text.strip():
                segments.append(dict(start=offset, end=end, text=text, words=[]))
            offset = end
    return dict(segments=segments, timing_quality='approximate',
                raw_asr_text=' '.join(s['text'] for s in segments),
                model='TeamUNIVA/qwen3_asr_1.7b_ko', precision='float16', vad=False,
                decoding={'language': 'Korean', 'chunk_seconds': 25, 'max_new_tokens': 512})


def diarize(args):
    import torch
    import soundfile as sf
    from transformers import AutoProcessor, AutoModelForAudioFrameClassification
    torch.set_num_threads(4)
    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForAudioFrameClassification.from_pretrained(args.model, dtype=torch.float16).to('cuda').eval()
    audio, rate = sf.read(args.audio, dtype='float32')
    if rate != 16000 or audio.ndim != 1:
        raise ValueError('Diarization expects normalized 16 kHz mono WAV')
    # Native offline mode internally chunks the encoder (340 + 40 frames).
    # Input features still grow with duration in file-based offline mode.
    inputs = processor(audio, sampling_rate=rate).to('cuda', dtype=torch.float16)
    with torch.inference_mode():
        logits = model(**inputs).logits
    if not torch.isfinite(logits).all():
        raise RuntimeError('Non-finite diarization output')
    segments = processor.extract_speaker_dict(logits, inputs.attention_mask)[0]
    return dict(turns=[dict(start=float(s['Start']), end=float(s['End']), speaker_id=f"speaker_{s['Speaker']}")
                       for s in segments], model='nvidia/Nemotron-3-Diarization',
                diarization_mode='native_offline', precision='float16',
                diarization_parameters={key: getattr(model.config, key) for key in
                    ['chunk_length', 'chunk_right_context', 'fifo_length', 'speaker_cache_update_period']})


def main():
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['asr', 'diarize'])
    p.add_argument('--audio', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--profile', choices=['moss', 'whisper-int8', 'whisper-fp16', 'qwen-ko'], default='moss')
    args = p.parse_args()
    # Cache paths are required; do not silently download a model during a job.
    if not Path(args.model).is_dir():
        p.error(f'Model directory does not exist: {args.model}')
    os.environ['HF_HUB_OFFLINE'] = '1'
    result = asr(args) if args.stage == 'asr' else diarize(args)
    revision_keys = {
        'OpenMOSS-Team/MOSS-Transcribe-Diarize': ('MEETING_MOSS_REVISION', '704aa4a9c304e8520be88901e0d1960158ef5b15'),
        'Systran/faster-whisper-large-v3': ('MEETING_WHISPER_REVISION', 'edaa852ec7e145841d8ffdb056a99866b5f0a478'),
        'TeamUNIVA/qwen3_asr_1.7b_ko': ('MEETING_QWEN_REVISION', '3e66f586033753589c3effeb2c8cbce46a1ddabb'),
        'nvidia/Nemotron-3-Diarization': ('MEETING_DIAR_REVISION', 'f667ed73aee57d40cc39428eb768b4fd87a0a29e'),
    }
    variable, default_revision = revision_keys[result['model']]
    result['model_provenance'] = {
        'model_id': result['model'], 'declared_revision': os.environ.get(variable, default_revision),
        'weights_verified': False, 'verification': 'Local model weights were not hashed or verified against the declared revision.'
    }
    import importlib.metadata
    result['runtime_versions'] = {}
    for package in ['torch', 'transformers', 'faster-whisper', 'ctranslate2', 'qwen-asr', 'moss-transcribe-diarize', 'jinja2']:
        try:
            result['runtime_versions'][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
