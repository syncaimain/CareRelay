"""Synthesize genuine Kokoro narration and align each segment to the actual video."""
import argparse
import json
import subprocess
import textwrap
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from kokoro import KPipeline

ROOT = Path(__file__).resolve().parent.parent


def stamp(seconds):
    millis = round(seconds * 1000)
    return f'{millis//3600000:02}:{millis//60000%60:02}:{millis//1000%60:02},{millis%1000:03}'


def main(voice):
    voices = json.loads((ROOT / 'docs/kokoro-voices.json').read_text())['english_voices']
    if voice not in voices:
        raise ValueError('Choose a verified supported English voice.')
    torch.set_num_threads(4)
    pipeline = KPipeline(lang_code=voice[0], repo_id='hexgrad/Kokoro-82M', device='cpu')
    segments = json.loads((ROOT / 'demo/narration_segments.json').read_text())
    work = ROOT / 'data/narration'
    work.mkdir(parents=True, exist_ok=True)
    length = 118.8
    rate = 24000
    master = np.zeros(round(length * rate), dtype=np.float32)
    cues = []
    measurements = []
    for index, segment in enumerate(segments):
        raw = np.concatenate([audio.numpy() for _, _, audio in pipeline(segment['text'], voice=voice, speed=1.0)])
        # FFmpeg tempo correction preserves pitch and leaves the actual footage unchanged.
        window = segment['end'] - segment['start'] - 0.08
        raw_seconds = len(raw) / rate
        factor = max(1.0, raw_seconds / window)
        if factor > 1.6:
            raise ValueError(f'Segment {index+1} would sound rushed ({factor:.2f}); shorten the script.')
        raw_path = work / f'{index:02}-raw.wav'
        fitted_path = work / f'{index:02}-fitted.wav'
        sf.write(raw_path, raw, rate)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(raw_path), '-af', f'atempo={factor:.6f}',
                        '-ar', str(rate), str(fitted_path)], check=True)
        audio, _ = sf.read(fitted_path, dtype='float32')
        offset = round(segment['start'] * rate)
        master[offset:offset+len(audio)] += audio
        end = segment['start'] + len(audio) / rate
        # Each caption is a readable two-line phrase; timing is proportional within
        # its independently synthesized and aligned speech segment.
        words = segment['text'].split()
        groups = [' '.join(words[i:i+12]) for i in range(0, len(words), 12)]
        cursor = segment['start']
        for group in groups:
            cue_end = cursor + (end-segment['start']) * len(group.split()) / len(words)
            cues.append(f'{len(cues)+1}\n{stamp(cursor)} --> {stamp(cue_end)}\n{textwrap.fill(group, width=58)}\n')
            cursor = cue_end
        measurements.append({'segment':index+1,'start':segment['start'],'end':round(end,3),
                             'raw_seconds':round(raw_seconds,3),'tempo_factor':round(factor,4)})
        print(f'Segment {index+1}/{len(segments)} aligned at {segment["start"]:.1f}s; tempo {factor:.2f}',flush=True)
    audio_dir = ROOT / 'demo/assets/audio'
    sf.write(audio_dir / 'kokoro_voiceover.wav', np.clip(master,-1,1), rate, subtype='PCM_16')
    (audio_dir / 'subtitles.srt').write_text('\n'.join(cues),encoding='utf-8')
    script = '# CareRelay narration\n\nVoice: `' + voice + '` · genuine hexgrad/Kokoro-82M · CPU · 24 kHz.\n\n'
    script += '\n\n'.join(f'**{s["start"]:.1f}–{s["end"]:.1f} seconds**\n\n{s["text"]}' for s in segments)
    (audio_dir / 'narration_script.md').write_text(script+'\n',encoding='utf-8')
    (ROOT / 'docs/narration-verification.json').write_text(json.dumps({
        'model':'hexgrad/Kokoro-82M','voice':voice,'user_direction':'use a non common voice; selection delegated',
        'sample_rate':rate,'seconds':length,'device':'cpu','segments':measurements,
        'subtitle_timing':'phrase timing proportional within each aligned TTS segment',
    },indent=2),encoding='utf-8')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--voice', required=True)
    main(parser.parse_args().voice)
