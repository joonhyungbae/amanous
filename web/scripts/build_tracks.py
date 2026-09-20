#!/usr/bin/env python3
"""
Build the player's assets from the repository's compositions.

For every track in the player this writes
  web/public/data/<id>.json   notes as [onset s, MIDI key, velocity] and the section layout
  web/public/audio/<id>.mp3   from the WAV render in audio_hq/
  web/public/midi/<id>.mid    a copy of the MIDI file, offered for download

Run from anywhere:  python web/scripts/build_tracks.py
"""
import csv
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'code'))

import amanous_composer as ac            # noqa: E402
import amanous_v2 as v2                  # noqa: E402
import custom_composition as cc          # noqa: E402


def v1_layout(config):
    out, t = [], 0.0
    for symbol, _ in ac.expand_lsystem(config.axiom, config.production_rules, config.iterations):
        d = config.symbol_configs[symbol].duration
        out.append({'symbol': symbol, 'start': t, 'end': t + d})
        t += d
    return out


def v2_layout(preset):
    v2.compose(preset())
    return [{'symbol': s, 'depth': d, 'start': a, 'end': b} for s, d, a, b, _ in v2.compose.last_layout]


TRACKS = {
    'beyond_human_demo': ('code/beyond_human_demo', 'audio_hq/beyond_human.wav',
                          lambda: v1_layout(ac.get_beyond_human_demo_config())),
    'minimalist_phase': ('compositions/minimalist_phase', 'audio_hq/minimalist_phase.wav',
                         lambda: v1_layout(cc.create_minimalist_composition())),
    'canonical_abaababa': ('code/canonical_abaababa', 'audio_hq/canonical_abaababa.wav',
                           lambda: v1_layout(ac.get_canonical_config())),
    'convergence_point': ('code/convergence_point', 'audio_hq/convergence_point.wav',
                          lambda: v1_layout(ac.get_convergence_point_config())),
    'v2_study_1': ('compositions/v2_study_1', 'audio_hq/v2_study_1.wav', lambda: v2_layout(v2.study_1)),
    'v2_study_2': ('compositions/v2_study_2', 'audio_hq/v2_study_2.wav', lambda: v2_layout(v2.study_2)),
}


def main():
    pub = os.path.join(ROOT, 'web', 'public')
    for sub in ('data', 'audio', 'midi'):
        os.makedirs(os.path.join(pub, sub), exist_ok=True)
    for tid, (stem, wav, layout) in TRACKS.items():
        with open(os.path.join(ROOT, stem + '_events.csv')) as f:
            rows = list(csv.DictReader(f))
        notes = sorted([round(float(r['onset_time']), 3), int(float(r['pitch'])), int(float(r['velocity']))]
                       for r in rows)
        mp3 = os.path.join(pub, 'audio', tid + '.mp3')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', os.path.join(ROOT, wav),
                        '-codec:a', 'libmp3lame', '-q:a', '2', mp3], check=True)
        dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                    '-of', 'csv=p=0', mp3], capture_output=True, text=True).stdout)
        shutil.copy(os.path.join(ROOT, stem + '.mid'), os.path.join(pub, 'midi', tid + '.mid'))
        sections = [{**s, 'start': round(s['start'], 3), 'end': round(s['end'], 3)} for s in layout()]
        data = {'duration': round(dur, 3), 'music_end': sections[-1]['end'], 'n_notes': len(notes),
                'key_range': [min(n[1] for n in notes), max(n[1] for n in notes)],
                'sections': sections, 'notes': notes}
        with open(os.path.join(pub, 'data', tid + '.json'), 'w') as f:
            json.dump(data, f, separators=(',', ':'))
        print(f"{tid:20s} {len(notes):5d} notes  {dur:6.1f} s  {os.path.getsize(mp3) / 1e6:4.1f} MB mp3  "
              f"{''.join(s['symbol'] for s in sections)}")


if __name__ == '__main__':
    main()
