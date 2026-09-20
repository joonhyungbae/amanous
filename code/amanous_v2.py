#!/usr/bin/env python3
"""
Amanous v2 -- post-paper development of the rule-based composer.

This module is NOT used by the published paper. The paper's presets and numbers live in
amanous_composer.py and are left untouched. v2 keeps the same four-layer idea (grammar ->
regime -> events -> hardware) and the same Layer 4, and changes what happens inside Layer 3,
where the published generator samples every note independently.

What v2 adds
  Layer 1  Sections are tagged by their position in the derivation tree (the rewrite at which
           a symbol was *born*), so sections of one piece really do differ in depth.
  Layer 2  A symbol selects a regime: 'canon' (melodic) or 'cloud' (textural), a chord
           progression, a register and a dynamic arc.
  Layer 3  canon: one motif, built by a constrained random walk over scale degrees, is stated by
                  every voice at its own tempo ratio. This is a tempo canon in the strict sense
                  (same material, different rates). The motif is transformed from statement to
                  statement (transposition to the current chord, inversion, retrograde), phrases
                  end in rests, and section lengths are chosen so the voices converge at the
                  section boundary, which is marked by an accented chord.
           cloud: a stochastic texture whose pitches walk inside the current chord-scale and
                  whose density and loudness follow an arc, so the cloud swells and recedes.
           Velocities follow phrase and section arcs with metric accents, articulation varies,
           and the sustain pedal is changed with the harmony.
  Layer 4  Latency pre-compensation as before. The key-reset mask first tries to move an
           offending note to a free key of the same pitch class in a neighbouring octave, and
           suppresses it only if no such key is free.

Usage
  python amanous_v2.py --preset study_1 --output ../compositions/v2_study_1.mid
  python amanous_v2.py --preset study_2 --seed 7
"""
import argparse
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from midiutil import MIDIFile

import amanous_composer as ac

KEY_LOW, KEY_HIGH = 21, 108
MODES = {
    'ionian': [0, 2, 4, 5, 7, 9, 11], 'dorian': [0, 2, 3, 5, 7, 9, 10],
    'lydian': [0, 2, 4, 6, 7, 9, 11], 'aeolian': [0, 2, 3, 5, 7, 8, 10],
    'pentatonic': [0, 2, 4, 7, 9],
}


# ----------------------------------------------------------------------------- configuration

@dataclass
class Regime:
    kind: str                       # 'canon' or 'cloud'
    progression: List[int]          # chord roots as scale degrees (0 = tonic), one per harmonic bar
    pulse: float = 0.06             # seconds per motif pulse at tempo ratio 1 (canon)
    ratios: Tuple[float, ...] = (3.0, 4.0)   # tempo ratios of the canon voices
    registers: Tuple[int, ...] = (48, 72)    # centre key of each voice
    cycles: int = 1                 # number of convergence cycles the section lasts (canon)
    duration: float = 8.0           # seconds (cloud)
    density: float = 60.0           # peak notes/s (cloud)
    level: int = 600                # central velocity on the 10-bit scale
    doublings: int = 0              # extra octave doublings per canon voice


@dataclass
class PieceConfig:
    title: str
    axiom: str
    rules: Dict[str, str]
    iterations: int
    regimes: Dict[str, Regime]
    tonic: int = 0                  # pitch class of the tonic
    mode: str = 'ionian'
    motif_length: int = 7
    seed: int = 42


# ----------------------------------------------------------------------------- Layer 1

def expand_with_birth(axiom: str, rules: Dict[str, str], iterations: int) -> List[Tuple[str, int]]:
    """L-system expansion that records where in the derivation tree each symbol was born.

    Parallel rewriting replaces every symbol at every step, so tagging a symbol with the index
    of the rewrite that produced it gives every symbol of the final string the same tag. Here
    the first symbol of a replacement continues its parent and inherits the parent's birth,
    while any further symbol is new and is born at the current rewrite. Sections therefore
    carry different depths within one piece.
    """
    current = [(s, 0) for s in axiom]
    for g in range(1, iterations + 1):
        nxt = []
        for symbol, birth in current:
            for j, s in enumerate(rules.get(symbol, symbol)):
                nxt.append((s, birth if j == 0 else g))
        current = nxt
    return current


# ----------------------------------------------------------------------------- pitch helpers

class Scale:
    def __init__(self, tonic: int, mode: str):
        self.tonic, self.steps = tonic, MODES[mode]
        self.n = len(self.steps)

    def key(self, degree: int) -> int:
        """MIDI key of an absolute scale degree (degree 0 = tonic in octave 0)."""
        octave, d = divmod(degree, self.n)
        return 12 * octave + self.tonic + self.steps[d]

    def degree_near(self, key: int) -> int:
        """Absolute scale degree whose key is closest to `key`."""
        guess = int(round((key - self.tonic) * self.n / 12))
        return min(range(guess - 3, guess + 4), key=lambda d: abs(self.key(d) - key))

    def chord_degrees(self, root: int) -> List[int]:
        return [root, root + 2, root + 4]


def make_motif(rng, length: int) -> List[Tuple[int, int]]:
    """A motif as (scale-degree offset from its first note, duration in pulses).

    Steps dominate, a leap is followed by a step in the opposite direction, the line stays
    within an octave, and the rhythm mixes short and long values with a long final note.
    """
    offsets, position, last = [0], 0, 0
    while len(offsets) < length:
        if abs(last) >= 3:
            step = -int(np.sign(last)) * int(rng.integers(1, 3))        # recover from a leap
        else:
            step = int(rng.choice([-2, -1, 1, 2, 3, -3, 4], p=[.08, .36, .36, .08, .05, .04, .03]))
        if abs(position + step) > 7:
            step = -step
        position += step
        last = step
        offsets.append(position)
    durations = [int(rng.choice([1, 1, 2, 1, 3])) for _ in range(length - 1)] + [4]
    return list(zip(offsets, durations))


def transform(motif, how: str):
    offsets = [o for o, _ in motif]
    durations = [d for _, d in motif]
    if how == 'inversion':
        offsets = [-o for o in offsets]
    elif how == 'retrograde':
        offsets = [o - offsets[-1] for o in offsets[::-1]]
        durations = durations[-2::-1] + [durations[-1]]
    return list(zip(offsets, durations))


# ----------------------------------------------------------------------------- Layer 3

def canon_section(regime: Regime, motif, scale: Scale, start: float, depth: int,
                  max_depth: int, rng) -> Tuple[List[Dict], float, List[Tuple[float, int]]]:
    """A strict tempo canon on one motif. Returns events, section end time and harmony changes."""
    motif_pulses = sum(d for _, d in motif) + 2                # +2 pulses of rest per statement
    ratios = regime.ratios
    # Voice i states the motif in motif_pulses * pulse / ratio_i seconds. With integer ratios the
    # voices realign after lcm(ratios) statements of the unit-rate stream.
    unit = motif_pulses * regime.pulse
    # The voices realign when n_i statements of voice i take the same time for every i, that is
    # n_i = ratio_i / gcd(ratios), after unit / gcd(ratios) seconds. For 3:4 the slower voice
    # has then stated the motif three times and the faster one four times.
    g = 0
    for r in ratios:
        g = math.gcd(g, int(r))
    cycle = unit / g
    duration = cycle * regime.cycles
    end = start + duration

    bars = len(regime.progression)
    bar_len = duration / bars
    harmony = [(start + b * bar_len, regime.progression[b]) for b in range(bars)]
    variants = ['plain', 'plain', 'inversion', 'plain', 'retrograde']
    ornament = depth / max(1, max_depth)                       # deeper sections are busier

    events = []
    for v, ratio in enumerate(ratios):
        pulse = regime.pulse / ratio
        centre = scale.degree_near(regime.registers[v % len(regime.registers)])
        t, statement = start, 0
        while t < end - 1e-9:
            root = regime.progression[min(bars - 1, int((t - start) / bar_len))]
            m = transform(motif, variants[(statement + v) % len(variants)])
            n_notes = len(m)
            for k, (offset, dur) in enumerate(m):
                if t >= end - 1e-9:
                    break
                degree = centre + root + offset
                phrase = math.sin(math.pi * (k + 0.5) / n_notes)               # phrase arc
                section = math.sin(math.pi * min(1.0, (t - start) / duration))  # section arc
                accent = 60 if k == 0 else (25 if k % 2 == 0 else 0)
                vel = regime.level + 170 * phrase + 160 * section + accent + rng.normal(0, 12) - 160
                length = dur * pulse
                gate = 1.05 if k < n_notes - 1 else 0.8                          # legato, then release
                keys = [scale.key(degree)] + [scale.key(degree) + 12 * (j + 1)
                                              for j in range(regime.doublings)]
                # a turn re-strikes its main key after two thirds of the note, so it is only used
                # where that leaves the key time to reset
                if ornament > 0.5 and dur >= 2 and 2 * length / 3 >= 0.06 and rng.random() < ornament * 0.6:
                    # deeper sections fill long notes with an upper-neighbour turn
                    sub = length / 3
                    for j, o in enumerate((0, 1, 0)):
                        events.append(_note(t + j * sub, scale.key(degree + o), vel - 40 * (j == 1),
                                            sub * 1.0, v))
                else:
                    for j, key in enumerate(keys):
                        # a doubling is its own voice, so that each line stays a single melody
                        events.append(_note(t, key, vel - 60 * (j > 0), length * gate, v + 100 * j))
                t += length
            t += 2 * pulse                                                       # breath
            statement += 1

    # convergence: all voices arrive together, marked by an accented chord on the next harmony
    return events, end, harmony


def cloud_section(regime: Regime, scale: Scale, start: float, depth: int, max_depth: int,
                  rng) -> Tuple[List[Dict], float, List[Tuple[float, int]]]:
    """A stochastic texture that walks inside the current chord-scale and swells."""
    duration = regime.duration
    end = start + duration
    bars = len(regime.progression)
    bar_len = duration / bars
    harmony = [(start + b * bar_len, regime.progression[b]) for b in range(bars)]
    peak = regime.density * (1 + 0.5 * depth / max(1, max_depth))

    events = []
    low, high = scale.degree_near(regime.registers[0]), scale.degree_near(regime.registers[-1])
    walkers = [int(rng.integers(low, high)) for _ in range(4)]
    t = start
    while t < end:
        x = (t - start) / duration
        arc = 0.15 + 0.85 * math.sin(math.pi * x) ** 2                       # swell and recede
        rate = max(4.0, peak * arc)
        t += rng.exponential(1.0 / rate)
        if t >= end:
            break
        w = int(rng.integers(0, len(walkers)))
        walkers[w] = int(np.clip(walkers[w] + rng.choice([-2, -1, 1, 2, 5, -5], p=[.2, .25, .25, .2, .05, .05]),
                                 low, high))
        root = regime.progression[min(bars - 1, int((t - start) / bar_len))]
        degree = walkers[w]
        if rng.random() < 0.5:                                               # lean on chord tones
            chord = scale.chord_degrees(root)
            degree = min((degree + s for s in range(-2, 3)),
                         key=lambda d: min(abs((d - c) % scale.n) for c in chord))
        vel = regime.level - 260 + 480 * arc + rng.normal(0, 40)
        events.append(_note(t, scale.key(degree), vel, 0.12 + 0.5 * (1 - arc), 10 + w))
    return events, end, harmony


def _note(t: float, key: int, vel_xp: float, duration: float, voice: int) -> Dict:
    vel_xp = float(np.clip(vel_xp, 60, 1000))
    return {'onset_time': float(t), 'pitch': int(np.clip(key, KEY_LOW, KEY_HIGH)),
            'velocity_xp': vel_xp, 'velocity': int(np.clip(round(vel_xp / 8), 1, 127)),
            'duration': float(duration), 'voice_id': int(voice)}


# ----------------------------------------------------------------------------- Layer 4

def key_reset_reallocate(events: List[Dict], reset_s: float = ac.KEY_RESET_S) -> Tuple[List[Dict], int, int]:
    """Key-reset constraint with reallocation.

    A trigger that would re-strike a key within `reset_s` is moved to a free key of the same
    pitch class one or two octaves away, which keeps the density and the pitch-class content.
    It is suppressed only when no such key is free. Returns (events, n_moved, n_suppressed).
    """
    last: Dict[int, float] = {}
    out, moved, dropped = [], 0, 0
    for e in sorted(events, key=lambda x: x['trigger_time']):
        t = e['trigger_time']

        def free(k):
            return KEY_LOW <= k <= KEY_HIGH and (k not in last or t - last[k] >= reset_s - 1e-9)

        key = e['pitch']
        if not free(key):
            for shift in (12, -12, 24, -24):
                if free(key + shift):
                    key += shift
                    moved += 1
                    break
            else:
                dropped += 1
                continue
        last[key] = t
        out.append({**e, 'pitch': key})
    return out, moved, dropped


def clip_same_key_overlaps(events: List[Dict], gap: float = 0.005) -> None:
    """Shorten a note that would still be held when the same key is struck again."""
    by_key: Dict[int, List[Dict]] = {}
    for e in sorted(events, key=lambda x: x['trigger_time']):
        by_key.setdefault(e['pitch'], []).append(e)
    for notes in by_key.values():
        for a, b in zip(notes, notes[1:]):
            a['duration'] = max(0.02, min(a['duration'], b['trigger_time'] - a['trigger_time'] - gap))


# ----------------------------------------------------------------------------- pipeline

def compose(config: PieceConfig) -> Tuple[List[Dict], List[Tuple[float, int]], str]:
    rng = np.random.default_rng(config.seed)
    scale = Scale(config.tonic, config.mode)
    motif = make_motif(rng, config.motif_length)
    sections = expand_with_birth(config.axiom, config.rules, config.iterations)
    max_depth = max(b for _, b in sections) or 1

    events, pedal, t = [], [], 0.0
    layout = []
    for symbol, birth in sections:
        regime = config.regimes[symbol]
        build = canon_section if regime.kind == 'canon' else cloud_section
        args = (regime, motif, scale, t, birth, max_depth, rng) if regime.kind == 'canon' \
            else (regime, scale, t, birth, max_depth, rng)
        ev, end, harmony = build(*args)
        # convergence chord at the head of every section after the first
        if layout:
            root = regime.progression[0]
            for d in scale.chord_degrees(scale.degree_near(36) + root) + \
                    scale.chord_degrees(scale.degree_near(60) + root):
                ev.append(_note(t, scale.key(d), 820, 0.9, 20))
        events += ev
        pedal += harmony
        layout.append((symbol, birth, t, end, len(ev)))
        t = end

    for e in events:
        e['trigger_time'] = e['onset_time'] - ac.latency_linear(e['velocity']) / 1000.0
    n_layer3 = len(events)
    events, moved, dropped = key_reset_reallocate(events)
    clip_same_key_overlaps(events)
    events.sort(key=lambda e: e['trigger_time'])

    lines = [f"=== Amanous v2: {config.title} ===",
             f"Sections: {''.join(s for s, _ in sections)}   duration {t:.1f} s   seed {config.seed}",
             f"Motif (degree offset, pulses): {motif}",
             f"Events: {len(events)} (Layer 3 produced {n_layer3}; key-reset moved {moved}, suppressed {dropped})"]
    for symbol, birth, a, b, n in layout:
        lines.append(f"  {symbol} depth {birth}  {a:6.1f}-{b:6.1f} s  {n:5d} events  {n / (b - a):6.1f} notes/s")
    return events, pedal, "\n".join(lines)


def write_midi(events: List[Dict], pedal: List[Tuple[float, int]], path: str, title: str, tempo: int = 120):
    midi = MIDIFile(1, deinterleave=False)
    midi.addTempo(0, 0, tempo)
    midi.addTrackName(0, 0, title.encode('ascii', 'ignore').decode('ascii'))
    beats = tempo / 60.0
    t0 = min(0.0, min(e['trigger_time'] for e in events))
    for e in events:
        midi.addNote(0, 0, e['pitch'], (e['trigger_time'] - t0) * beats,
                     max(0.02, e['duration']) * beats, e['velocity'])
    for t, _ in pedal:                                   # re-pedal at every harmony change
        midi.addControllerEvent(0, 0, max(0.0, (t - t0 - 0.03)) * beats, 64, 0)
        midi.addControllerEvent(0, 0, (t - t0 + 0.03) * beats, 64, 127)
    end = max(e['trigger_time'] + e['duration'] for e in events) - t0
    midi.addControllerEvent(0, 0, (end + 0.5) * beats, 64, 0)
    with open(path, 'wb') as f:
        midi.writeFile(f)


# ----------------------------------------------------------------------------- presets

def study_1() -> PieceConfig:
    """Canon 3:4 against swelling clouds, C lydian, Fibonacci form ABAABABA."""
    return PieceConfig(
        title="Amanous v2, Study 1 (Canon 3:4)", axiom='A', rules={'A': 'AB', 'B': 'A'}, iterations=4,
        tonic=0, mode='lydian', motif_length=7, seed=42,
        regimes={
            'A': Regime('canon', progression=[0, 5, 3, 4], pulse=0.12, ratios=(3.0, 4.0),
                        registers=(50, 74), cycles=6, level=560, doublings=1),
            'B': Regime('cloud', progression=[3, 4, 1, 0], duration=9.0, density=70.0,
                        registers=(36, 96), level=600),
        })


def study_2() -> PieceConfig:
    """Three-voice canon 4:5:6 in D dorian, thirteen shorter sections."""
    return PieceConfig(
        title="Amanous v2, Study 2 (Canon 4:5:6)", axiom='A', rules={'A': 'AB', 'B': 'A'}, iterations=5,
        tonic=2, mode='dorian', motif_length=6, seed=42,
        regimes={
            'A': Regime('canon', progression=[0, 3, 6, 4], pulse=0.16, ratios=(4.0, 5.0, 6.0),
                        registers=(43, 62, 81), cycles=3, level=540, doublings=0),
            'B': Regime('cloud', progression=[4, 0], duration=5.0, density=90.0,
                        registers=(30, 100), level=640),
        })


PRESETS = {'study_1': study_1, 'study_2': study_2}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--preset', choices=sorted(PRESETS), default='study_1')
    ap.add_argument('--seed', type=int, default=None)
    ap.add_argument('--output', default=None)
    a = ap.parse_args()
    cfg = PRESETS[a.preset]()
    if a.seed is not None:
        cfg.seed = a.seed
    out = a.output or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'compositions',
                                   f'v2_{a.preset}.mid')
    ev, ped, summary = compose(cfg)
    print(summary)
    write_midi(ev, ped, out, cfg.title)
    import pandas as pd
    pd.DataFrame(ev).to_csv(out.replace('.mid', '_events.csv'), index=False)
    print(f"MIDI saved: {out}")
