"""Generate three genuine voice samples, without selecting a final narrator."""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from kokoro import KPipeline

torch.set_num_threads(4)
ROOT = Path(__file__).resolve().parent.parent
out = ROOT / 'demo/assets/audio/previews'
out.mkdir(parents=True, exist_ok=True)
text = 'CareRelay brings family messages into a shared, approved plan. Local AI, human accountability, and a little less to carry.'
american = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M', device='cpu')
british = KPipeline(lang_code='b', repo_id='hexgrad/Kokoro-82M', model=american.model, device='cpu')
for voice in ['af_heart', 'bf_emma', 'am_michael']:
    pipeline = british if voice.startswith('b') else american
    chunks = [audio.numpy() for _, _, audio in pipeline(text, voice=voice, speed=1)]
    audio = np.concatenate(chunks)
    sf.write(out / (voice + '.wav'), audio, 24000)
    print(f'{voice}: {len(audio)/24000:.2f}s', flush=True)
(ROOT / 'docs/kokoro-runtime.json').write_text(json.dumps({
    'repo': 'hexgrad/Kokoro-82M', 'device': 'cpu', 'torch': torch.__version__,
    'sample_rate': 24000, 'preview_voices': ['af_heart', 'bf_emma', 'am_michael'],
    'final_voice_selected': False,
}, indent=2), encoding='utf-8')
