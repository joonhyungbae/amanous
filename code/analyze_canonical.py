#!/usr/bin/env python3
"""
Canonical-instantiation analysis
================================

Regenerates the canonical ABAABABA composition with amanous_composer and computes
every quantity the paper reports for it:

  * per-symbol event counts, section durations and aggregate densities
  * the distribution-switching signature (pitch-class set and velocity support per symbol)
  * registral separation between the two voices in the deterministic sections
  * Melodic and Rhythmic Coherence for same-symbol versus cross-symbol section pairs
  * Pitch-Class Concentration per section, compared across symbols
  * per-layer distributional degradation (KS distance, intended versus realized,
    measured after Layer 2, Layer 3 and Layer 4)

Everything is derived from a single seeded run. Results are written to
canonical_analysis.json next to this file.

Usage:  python analyze_canonical.py [--seed 42]
"""

import argparse
import json
from collections import Counter
from itertools import combinations

import numpy as np
from scipy import stats

import amanous_composer as ac
from config import CODE_DIR


# ---------------------------------------------------------------- metrics

def contour(pitches):
    """Up/Down/Same contour string of a pitch sequence."""
    out = []
    for a, b in zip(pitches[:-1], pitches[1:]):
        out.append('U' if b > a else ('D' if b < a else 'S'))
    return ''.join(out)


def levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def melodic_coherence(x, y):
    """1 - normalized Levenshtein distance between pitch contours (Equation: MC)."""
    cx, cy = contour(x), contour(y)
    if not cx or not cy:
        return float('nan')
    return 1.0 - levenshtein(cx, cy) / max(len(cx), len(cy))


def rhythmic_coherence(x, y):
    """1 - KS distance between two IOI distributions (Equation: RC)."""
    if len(x) < 2 or len(y) < 2:
        return float('nan')
    return 1.0 - stats.ks_2samp(x, y).statistic


def pitch_class_concentration(pitches):
    """PCC = 1 - H(pitch class) / log2(12)."""
    counts = Counter(p % 12 for p in pitches)
    total = sum(counts.values())
    h = -sum((c / total) * np.log2(c / total) for c in counts.values() if c)
    return 1.0 - h / np.log2(12)


def cohens_d(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    return (a.mean() - b.mean()) / sp if sp > 0 else float('nan')


def d_ci(d, na, nb):
    """95% CI for Cohen's d via the normal approximation of its standard error."""
    se = np.sqrt((na + nb) / (na * nb) + d ** 2 / (2 * (na + nb)))
    return d - 1.96 * se, d + 1.96 * se


# ---------------------------------------------------------------- sectioning

def build_sections(config):
    """Replay Layer 1 and Layer 2 to recover the section timeline the composer used."""
    expanded = ac.expand_lsystem(config.axiom, config.production_rules, config.iterations)
    max_gen = max((g for _, g in expanded), default=1)
    sections, t = [], 0.0
    for symbol, generation in expanded:
        sc = ac.apply_depth_weight_to_config(config.symbol_configs[symbol], generation, max_gen)
        sections.append({'symbol': symbol, 'generation': generation,
                         'start': t, 'end': t + sc.duration, 'config': sc})
        t += sc.duration
    return sections


def section_of(sections, onset):
    for i, s in enumerate(sections):
        if s['start'] <= onset < s['end']:
            return i
    return len(sections) - 1


# ---------------------------------------------------------------- degradation

def intended_ioi_sample(sc, tempo_ratio, n, rng, clip=True):
    """
    The IOI distribution the design specifies for one voice of one section.

    `clip` mirrors the generator's floor of 10 ms, which is applied after tempo
    scaling. It must be off when comparing against the Layer-2 samples, which are
    drawn before that floor is imposed.
    """
    d = sc.ioi_dist
    if d.dist_type == 'constant':
        base = np.full(n, d.params['value'])
    elif d.dist_type == 'exponential':
        base = rng.exponential(d.params['scale'], size=n)
    elif d.dist_type == 'uniform':
        base = rng.uniform(d.params['low'], d.params['high'], size=n)
    elif d.dist_type == 'gaussian':
        base = rng.normal(d.params['mean'], d.params['std'], size=n)
    else:
        raise ValueError(d.dist_type)
    scaled = base / tempo_ratio
    return np.maximum(0.01, scaled) if clip else scaled


def _degenerate(x, rtol=1e-9):
    """True when a sample has no spread beyond floating-point accumulation error."""
    m = np.abs(np.mean(x))
    return np.std(x) <= rtol * max(m, 1e-12)


def ks_or_zero(sample, reference):
    """
    KS distance between a realized sample and the intended distribution.

    A constant distribution realized exactly still accumulates floating-point error
    in the onset sum, which ks_2samp would report as a large statistic against a
    perfectly constant reference. Degenerate cases are therefore compared by value.
    """
    sample, reference = np.asarray(sample, float), np.asarray(reference, float)
    if sample.size < 2 or reference.size < 2:
        return float('nan')
    # Onsets are accumulated by repeated addition, so an interval the generator
    # clipped to exactly 10 ms comes back as 0.009999999999999998. Left alone, that
    # noise separates the realized atom from the intended one and the KS statistic
    # reports a difference of 0.3 where there is none. Quantize to nanoseconds,
    # which is far below the instrument's millisecond scanning resolution.
    sample = np.round(sample, 9)
    reference = np.round(reference, 9)
    if _degenerate(sample) and _degenerate(reference):
        return 0.0 if np.isclose(np.mean(sample), np.mean(reference), rtol=1e-6) else 1.0
    return float(stats.ks_2samp(sample, reference).statistic)


def intended_pitch_sample(sc, voice_id, voices, n, rng):
    """The pitch distribution the design specifies, including set-snapping and voice offset."""
    d = sc.pitch_dist
    if d.dist_type == 'gaussian':
        raw = rng.normal(d.params['mean'], d.params['std'], size=n)
    elif d.dist_type == 'uniform':
        raw = rng.uniform(d.params['low'], d.params['high'], size=n)
    else:
        raise ValueError(d.dist_type)
    out = []
    for r in raw:
        p = int(np.clip(r, 21, 108))
        if sc.pitch_set is not None and p % 12 not in sc.pitch_set:
            pc = p % 12
            dists = [min(abs(pc - q), 12 - abs(pc - q)) for q in sc.pitch_set]
            p = int(np.clip((p // 12) * 12 + sc.pitch_set[int(np.argmin(dists))], 21, 108))
        if sc.mode == 'melodic':
            p = int(np.clip(p + (voice_id - voices // 2) * 12, 21, 108))
        out.append(p)
    return np.array(out, float)


def intended_velocity_sample(sc, n, rng):
    """The velocity distribution the design specifies, on the 0-127 MIDI scale."""
    d = sc.velocity_dist
    if d.dist_type == 'constant':
        raw = np.full(n, d.params['value'])
    elif d.dist_type == 'uniform':
        raw = rng.uniform(d.params['low'], d.params['high'], size=n)
    elif d.dist_type == 'gaussian':
        raw = rng.normal(d.params['mean'], d.params['std'], size=n)
    else:
        raise ValueError(d.dist_type)
    return np.clip(raw / 8.0, 1, 127).astype(int).astype(float)


def degradation(raw_events, events, sections, voices, rng, n_ref=20000):
    """
    KS distance between the intended distribution and the realized one, measured
    after each layer. Computed per section and per voice, because Layer 2's
    depth weighting gives each section its own intended distribution, then averaged
    within a symbol.

    `raw_events` is the Layer 3 stream before Layer 4 touches it, and `events` is the
    final output. Layers 2 and 3 are measured on the former, Layer 4 on the latter, so
    that what Layer 4 does (latency pre-compensation, then the key-reset mask, which
    removes events) is charged to Layer 4 and to nothing upstream of it.
    """
    acc = {(p, s): {'L2': [], 'L3': [], 'L4c': [], 'L4': []}
           for p in ('IOI', 'Pitch', 'Velocity') for s in ('A', 'B')}

    for i, sec in enumerate(sections):
        sc, symbol = sec['config'], sec['symbol']
        ev = [e for e in raw_events if section_of(sections, e['onset_time']) == i]
        ev_out = [e for e in events if section_of(sections, e['onset_time']) == i]
        by_voice, by_voice_out = {}, {}
        for e in ev:
            by_voice.setdefault(e['voice_id'], []).append(e)
        for e in ev_out:
            by_voice_out.setdefault(e['voice_id'], []).append(e)

        for vid, ve in by_voice.items():
            ve.sort(key=lambda e: e['onset_time'])
            vo = by_voice_out.get(vid, [])
            ratio = ve[0]['tempo_ratio']

            # IOI. Layer 2 is the sampled base interval, Layer 3 adds tempo scaling,
            # Layer 4 is the spacing of the actual trigger times after compensation.
            base = np.array([e['base_ioi'] for e in ve])
            acc[('IOI', symbol)]['L2'].append(
                ks_or_zero(base, intended_ioi_sample(sc, 1.0, n_ref, rng, clip=False)))

            ref_scaled = intended_ioi_sample(sc, ratio, n_ref, rng)
            acc[('IOI', symbol)]['L3'].append(
                ks_or_zero(np.diff([e['onset_time'] for e in ve]), ref_scaled))
            # Layer 4, first stage only: latency pre-compensation on the full stream.
            comp = np.sort([e['onset_time'] - ac.latency_linear(e['velocity']) / 1000.0 for e in ve])
            acc[('IOI', symbol)]['L4c'].append(ks_or_zero(np.diff(comp), ref_scaled))
            # Layer 4 complete: compensation followed by the key-reset mask.
            acc[('IOI', symbol)]['L4'].append(
                ks_or_zero(np.diff(np.sort([e['trigger_time'] for e in vo])), ref_scaled))

            # Pitch and velocity are fixed at Layer 2 and are not rewritten downstream.
            # Layer 3 leaves them as they are. Layer 4 does not change any value either,
            # but its key-reset mask removes events, so the surviving sample is measured
            # separately.
            ref_p = intended_pitch_sample(sc, vid, voices, n_ref, rng)
            ref_v = intended_velocity_sample(sc, n_ref, rng)
            kp = ks_or_zero(np.array([e['pitch'] for e in ve], float), ref_p)
            kv = ks_or_zero(np.array([e['velocity'] for e in ve], float), ref_v)
            for layer in ('L2', 'L3', 'L4c'):
                acc[('Pitch', symbol)][layer].append(kp)
                acc[('Velocity', symbol)][layer].append(kv)
            acc[('Pitch', symbol)]['L4'].append(
                ks_or_zero(np.array([e['pitch'] for e in vo], float), ref_p))
            acc[('Velocity', symbol)]['L4'].append(
                ks_or_zero(np.array([e['velocity'] for e in vo], float), ref_v))

    rows = []
    for param in ('IOI', 'Pitch', 'Velocity'):
        for symbol in ('A', 'B'):
            a = acc[(param, symbol)]
            rows.append({
                'parameter': param, 'symbol': symbol,
                'after_L2': float(np.mean(a['L2'])),
                'after_L3': float(np.mean(a['L3'])),
                'after_L4_compensation_only': float(np.mean(a['L4c'])),
                'after_L4': float(np.mean(a['L4'])),
            })
    return rows


# ---------------------------------------------------------------- main

def main(seed):
    config = ac.get_canonical_config()
    config.seed = seed
    events, sequence, _ = ac.compose(config)
    # The same seed regenerates the identical Layer 3 stream with Layer 4 switched off.
    raw_events, _, _ = ac.compose(config, apply_hw_compensation=False)
    sections = build_sections(config)
    rng = np.random.default_rng(seed)

    per_section = []
    for i, s in enumerate(sections):
        ev = [e for e in events if section_of(sections, e['onset_time']) == i]
        ev.sort(key=lambda e: e['onset_time'])
        pitches = [e['pitch'] for e in ev]
        per_section.append({
            'index': i, 'symbol': s['symbol'], 'generation': s['generation'],
            'n_events': len(ev),
            'duration_s': s['end'] - s['start'],
            'density_nps': len(ev) / (s['end'] - s['start']),
            'pcc': pitch_class_concentration(pitches),
            'pitch_classes': sorted({p % 12 for p in pitches}),
            'n_velocities': len({e['velocity'] for e in ev}),
            'events': ev,
        })

    # ---- distribution-switching signature and densities
    summary = {}
    for symbol in ('A', 'B'):
        secs = [s for s in per_section if s['symbol'] == symbol]
        n = sum(s['n_events'] for s in secs)
        dur = sum(s['duration_s'] for s in secs)
        summary[symbol] = {
            'n_sections': len(secs),
            'n_events': n,
            'total_duration_s': dur,
            'aggregate_density_nps': n / dur,
            'pitch_classes': sorted({pc for s in secs for pc in s['pitch_classes']}),
            'n_distinct_velocities': len({e['velocity'] for s in secs for e in s['events']}),
        }

    # ---- registral separation in the deterministic (A) sections
    gaps = []
    for s in per_section:
        if s['symbol'] != 'A':
            continue
        v = {}
        for e in s['events']:
            v.setdefault(e['voice_id'], []).append(e['pitch'])
        if len(v) >= 2:
            means = [np.mean(v[k]) for k in sorted(v)]
            gaps.append(abs(means[0] - means[1]))
    registral_separation = float(np.mean(gaps)) if gaps else float('nan')

    # ---- MC / RC, same-symbol versus cross-symbol section pairs
    same_mc, cross_mc, same_rc, cross_rc = [], [], [], []
    for i, j in combinations(range(len(per_section)), 2):
        a, b = per_section[i], per_section[j]
        pa = [e['pitch'] for e in a['events']]
        pb = [e['pitch'] for e in b['events']]
        ia = np.diff([e['onset_time'] for e in a['events']])
        ib = np.diff([e['onset_time'] for e in b['events']])
        mc, rc = melodic_coherence(pa, pb), rhythmic_coherence(ia, ib)
        (same_mc if a['symbol'] == b['symbol'] else cross_mc).append(mc)
        (same_rc if a['symbol'] == b['symbol'] else cross_rc).append(rc)

    coherence = {}
    for name, same, cross in (('MC', same_mc, cross_mc), ('RC', same_rc, cross_rc)):
        t, p = stats.ttest_ind(same, cross)
        d = cohens_d(same, cross)
        lo, hi = d_ci(d, len(same), len(cross))
        coherence[name] = {
            'n_same': len(same), 'n_cross': len(cross),
            'same_mean': float(np.mean(same)), 'same_sd': float(np.std(same, ddof=1)),
            'cross_mean': float(np.mean(cross)), 'cross_sd': float(np.std(cross, ddof=1)),
            'gap': float(np.mean(same) - np.mean(cross)),
            'df': len(same) + len(cross) - 2, 't': float(t), 'p': float(p),
            'cohens_d': float(d), 'd_ci95': [float(lo), float(hi)],
        }

    # ---- PCC by symbol
    pcc_a = [s['pcc'] for s in per_section if s['symbol'] == 'A']
    pcc_b = [s['pcc'] for s in per_section if s['symbol'] == 'B']
    u, pu = stats.mannwhitneyu(pcc_a, pcc_b, alternative='two-sided')
    pcc = {
        'A_mean': float(np.mean(pcc_a)), 'A_sd': float(np.std(pcc_a, ddof=1)), 'n_A': len(pcc_a),
        'B_mean': float(np.mean(pcc_b)), 'B_sd': float(np.std(pcc_b, ddof=1)), 'n_B': len(pcc_b),
        'U': float(u), 'p': float(pu), 'cohens_d': float(cohens_d(pcc_a, pcc_b)),
    }

    # ---- density bifurcation across sections
    dens_a = [s['density_nps'] for s in per_section if s['symbol'] == 'A']
    dens_b = [s['density_nps'] for s in per_section if s['symbol'] == 'B']
    ud, pd_ = stats.mannwhitneyu(dens_a, dens_b, alternative='two-sided')

    result = {
        'seed': seed,
        'lsystem_sequence': sequence,
        'n_events_total': len(events),
        'n_events_layer3': len(raw_events),
        'n_suppressed_by_key_reset': len(raw_events) - len(events),
        'duration_s': max(e['onset_time'] + e['duration'] for e in events),
        'symbols': summary,
        'density_bifurcation': {
            'A_mean_nps': float(np.mean(dens_a)), 'B_mean_nps': float(np.mean(dens_b)),
            'gap_nps': float(np.mean(dens_b) - np.mean(dens_a)),
            'U': float(ud), 'p': float(pd_),
        },
        'registral_separation_semitones': registral_separation,
        'coherence': coherence,
        'pcc_by_symbol': pcc,
        'degradation': degradation(raw_events, events, sections, config.voices, rng),
        'per_section': [{k: v for k, v in s.items() if k != 'events'} for s in per_section],
    }

    out = CODE_DIR / 'canonical_analysis.json'
    with open(out, 'w') as f:
        json.dump(result, f, indent=2)

    # ---- console report
    print(f"L-system {sequence}   N = {result['n_events_total']} events   "
          f"{result['duration_s']:.2f} s   seed {seed}")
    for s in ('A', 'B'):
        d = summary[s]
        print(f"  symbol {s}: {d['n_events']:5d} events over {d['total_duration_s']:.0f}s "
              f"= {d['aggregate_density_nps']:6.1f} notes/s | "
              f"{len(d['pitch_classes'])} pitch classes | "
              f"{d['n_distinct_velocities']} velocities")
    print(f"  registral separation (A sections): {registral_separation:.1f} semitones")
    for name, c in coherence.items():
        print(f"  {name}: same {c['same_mean']:.3f}+-{c['same_sd']:.3f}  "
              f"cross {c['cross_mean']:.3f}+-{c['cross_sd']:.3f}  "
              f"t({c['df']}) = {c['t']:.2f}, p = {c['p']:.2e}, d = {c['cohens_d']:.2f} "
              f"[{c['d_ci95'][0]:.2f}, {c['d_ci95'][1]:.2f}]")
    print(f"  PCC: A {pcc['A_mean']:.4f}+-{pcc['A_sd']:.4f} (n={pcc['n_A']})  "
          f"B {pcc['B_mean']:.4f}+-{pcc['B_sd']:.4f} (n={pcc['n_B']})  "
          f"U = {pcc['U']:.1f}, p = {pcc['p']:.3f}, d = {pcc['cohens_d']:.2f}")
    print("  degradation (KS from intended):")
    for r in result['degradation']:
        print(f"    {r['parameter']:8s} {r['symbol']}  L2 {r['after_L2']:.3f}  "
              f"L3 {r['after_L3']:.3f}  L4 {r['after_L4']:.3f}")
    print(f"\nWrote {out}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seed', type=int, default=42)
    main(ap.parse_args().seed)
