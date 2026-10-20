import argparse
import json
import sys
from pathlib import Path

from providers import run_remote

parser = argparse.ArgumentParser()
parser.add_argument('--stage', choices=['transcription', 'diarization'], required=True)
parser.add_argument('--audio', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
# Credentials are passed over stdin, never command arguments or a job file.
config = json.load(sys.stdin)
result = run_remote(config, Path(args.audio), args.stage)
Path(args.output).write_text(json.dumps(result, ensure_ascii=False), encoding='utf8')
