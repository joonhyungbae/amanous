#!/usr/bin/env python3
"""
Compare the musical surface of the published generator (v1) with Amanous v2.

These are descriptive statistics of the note stream, not perceptual measures. They answer
whether the things v2 set out to add are actually present in its output: stepwise melodic
motion, recurring melodic material, silence, a used dynamic range, and a satisfied key-reset
constraint.

Usage: python v2_quality_report.py
"""
import collections
import json
import os

import numpy as np

import amanous_composer as ac
import amanous_v2 as v2


def describe(events, voices):
    out = {}
    steps, grams = [], collections.Counter()
    for v in voices:
        line = sorted((e for e in events if e['voice_id'] == v), key=lambda e: e['onset_time'])
        iv = np.diff([e['pitch'] for e in line])
        steps += list(iv)
        for k in range(len(iv) - 3):
            grams[tuple(iv[k:k + 4])] += 1
    steps = np.abs(np.array(steps))
    out['stepwise_share'] = float(np.mean((steps >= 1) & (steps <= 2)))
    out['leap_share_over_octave'] = float(np.mean(steps > 12))
    total = sum(grams.values())
    out['interval_4gram_repetition'] = float(sum(c for c in grams.values() if c > 1) / total)
    onsets = np.sort([e['onset_time'] for e in events])
    gaps = np.diff(onsets)
    out['silences_over_150ms'] = int(np.sum(gaps > 0.15))
    vel = np.array([e['velocity'] for e in events])
    out['velocity_range_used'] = [int(vel.min()), int(vel.max())]
    out['velocity_sd'] = float(vel.std())
    by = collections.defaultdict(list)
    for e in events:
        by[e['pitch']].append(e['trigger_time'])
    out['key_reset_violations'] = int(sum(b - a < 0.05 - 1e-6 for ts in by.values()
                                          for a, b in zip(sorted(ts), sorted(ts)[1:])))
    out['n_events'] = len(events)
    return out


if __name__ == '__main__':
    report = {}
    ev1, _, _ = ac.compose(ac.get_canonical_config())
    report['v1_canonical'] = describe(ev1, voices=[0, 1])
    for name, preset in v2.PRESETS.items():
        cfg = preset()
        ev, _, _ = v2.compose(cfg)
        n_voices = len(cfg.regimes['A'].ratios)
        report[f'v2_{name}'] = describe(ev, voices=list(range(n_voices)))
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'v2_quality_report.json')
    json.dump(report, open(path, 'w'), indent=2)
    keys = list(next(iter(report.values())))
    print(f"{'':28s}" + "".join(f"{k:>16s}" for k in report))
    for k in keys:
        print(f"{k:28s}" + "".join(f"{str(np.round(report[r][k], 3)):>16s}" for r in report))
