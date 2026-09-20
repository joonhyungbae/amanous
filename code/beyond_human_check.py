#!/usr/bin/env python3
"""
Check the beyond-human demonstration (paper Table "Beyond-human-density specifications").

The demonstration is three specified gestures, each written against a physical limit of
human performance: a 40-note simultaneity every 500 ms, a 30 Hz trill, and a six-octave
arpeggio at a 25 ms inter-onset interval. This script regenerates the piece with the
composer's preset, passes it through Layer 4 (latency pre-compensation and the 50 ms
key-reset mask), and reports for each gesture what was specified, what the MIDI event
stream realises, and how many events the key-reset mask had to suppress. It also reports
the pairwise Kolmogorov-Smirnov tests between the three sections.

Usage:  python beyond_human_check.py [--seed 42]
Writes: beyond_human_check.json
"""
import argparse
import collections
import itertools
import json
import os

import numpy as np
from scipy import stats

import amanous_composer as ac

GESTURES = {'P': 'polyphony', 'R': 'repetition', 'S': 'speed_span'}


def main(seed):
    config = ac.get_beyond_human_demo_config()
    config.seed = seed
    events, sequence, _ = ac.compose(config)
    raw, _, _ = ac.compose(config, apply_hw_compensation=False)

    bounds, t = [], 0.0
    for symbol, _ in ac.expand_lsystem(config.axiom, config.production_rules, config.iterations):
        d = config.symbol_configs[symbol].duration
        bounds.append((symbol, t, t + d))
        t += d

    out = {'seed': seed, 'sequence': sequence, 'n_events': len(events),
           'n_events_layer3': len(raw), 'sections': {}}
    samples = {}
    for symbol, a, b in bounds:
        if symbol not in GESTURES:
            continue
        ev = [e for e in events if a <= e['onset_time'] < b]
        rw = [e for e in raw if a <= e['onset_time'] < b]
        onsets = np.array(sorted({round(e['onset_time'], 9) for e in ev}))
        by_key = collections.defaultdict(list)
        for e in ev:
            by_key[e['pitch']].append(e['trigger_time'])
        gaps = [q - p for ts in by_key.values() for p, q in zip(sorted(ts), sorted(ts)[1:])]
        pitches = [e['pitch'] for e in ev]
        out['sections'][GESTURES[symbol]] = {
            'n_events': len(ev),
            'suppressed_by_key_reset': len(rw) - len(ev),
            'notes_per_onset': len(ev) / len(onsets),
            'onset_step_ms': [float(np.diff(onsets).min() * 1000), float(np.diff(onsets).max() * 1000)],
            'aggregate_rate_hz': len(ev) / (b - a),
            'n_keys': len(by_key),
            'span_semitones': int(max(pitches) - min(pitches)),
            'min_same_key_gap_ms': float(min(gaps) * 1000),
        }
        samples[GESTURES[symbol]] = {
            'ioi': np.diff(np.sort([e['trigger_time'] for e in ev])),
            'pitch': np.array(pitches, float),
            'velocity': np.array([e['velocity'] for e in ev], float),
        }

    out['between_section_ks'] = {}
    for x, y in itertools.combinations(samples, 2):
        out['between_section_ks'][f'{x}_vs_{y}'] = {
            k: {'D': float(stats.ks_2samp(samples[x][k], samples[y][k]).statistic),
                'p': float(stats.ks_2samp(samples[x][k], samples[y][k]).pvalue)}
            for k in ('ioi', 'pitch', 'velocity')}

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'beyond_human_check.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=2)
    for name, s in out['sections'].items():
        print(f"{name:11s} {s['n_events']:4d} events  {s['notes_per_onset']:.0f}/onset  "
              f"step {s['onset_step_ms'][0]:.1f} ms  {s['n_keys']} keys  span {s['span_semitones']}  "
              f"min same-key gap {s['min_same_key_gap_ms']:.1f} ms  suppressed {s['suppressed_by_key_reset']}")
    worst = max(v[k]['p'] for v in out['between_section_ks'].values() for k in v)
    print(f"largest between-section KS p-value: {worst:.3g}")
    print(f"Wrote {path}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seed', type=int, default=42)
    main(ap.parse_args().seed)
