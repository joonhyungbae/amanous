#!/usr/bin/env python3
"""
Amanous: Unified Parametric Framework for Algorithmic Piano Composition
========================================================================

A complete implementation of the hierarchical distribution-switching architecture
integrating L-Systems, Tempo Canons, and Stochastic Processes.

Based on: "A Unified Parametric Framework for Beyond-Human Piano Composition"
"""

import numpy as np
from midiutil import MIDIFile
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import os

# =============================================================================
# CONFIGURATION DATACLASSES
# =============================================================================

@dataclass
class DistributionConfig:
    """Configuration for a probability distribution."""
    dist_type: str  # 'constant', 'uniform', 'gaussian', 'exponential'
    params: Dict

@dataclass
class SymbolConfig:
    """Complete configuration for an L-System symbol."""
    tempo_ratios: Tuple[float, ...]  # Tempo ratios for each voice
    duration: float  # Section duration in seconds
    ioi_dist: DistributionConfig  # Inter-onset interval distribution
    pitch_dist: DistributionConfig  # Pitch distribution
    velocity_dist: DistributionConfig  # Velocity distribution
    pitch_set: Optional[List[int]] = None  # Allowed pitch classes (0-11)
    mode: str = 'melodic'  # 'melodic' or 'textural'
    # Optional specified gesture. When set, the section is built from this specification
    # ('chords', 'trill' or 'arpeggio') instead of being sampled voice by voice. Velocity is
    # still drawn from velocity_dist, and Layer 4 is applied as for any other section.
    gesture: Optional[str] = None

@dataclass
class CompositionConfig:
    """Complete composition configuration."""
    axiom: str
    production_rules: Dict[str, str]
    iterations: int
    symbol_configs: Dict[str, SymbolConfig]
    voices: int = 2
    seed: int = 42
    title: str = "Amanous Composition"

# =============================================================================
# LAYER 1: L-SYSTEM MACRO-FORM GENERATION
# =============================================================================

def generate_lsystem(axiom: str, rules: Dict[str, str], iterations: int) -> str:
    """Generate L-System string by applying production rules iteratively."""
    current = axiom
    for _ in range(iterations):
        next_string = ""
        for symbol in current:
            next_string += rules.get(symbol, symbol)
        current = next_string
    return current


def expand_lsystem(
    axiom: str, rules: Dict[str, str], iterations: int
) -> List[Tuple[str, int]]:
    """
    Expand L-system and return list of (symbol, generation).
    Generation = iteration index at which this symbol was produced:
      0 = axiom, 1 = first expansion, ..., iterations = last expansion.
    Used so Layer 2 can weight parameters by recursion depth (deeper → denser IOI, wider pitch).
    """
    current: List[Tuple[str, int]] = [(s, 0) for s in axiom]
    for g in range(1, iterations + 1):
        next_list: List[Tuple[str, int]] = []
        for symbol, _ in current:
            replacement = rules.get(symbol, symbol)
            for s in replacement:
                next_list.append((s, g))
        current = next_list
    return current

# =============================================================================
# LAYER 2: DISTRIBUTION-SWITCHING PARAMETER MAPPING
# =============================================================================

def apply_depth_weight_to_config(
    base: SymbolConfig,
    generation: int,
    max_generation: int,
    k_ioi: float = 0.5,
    k_pitch: float = 0.6,
) -> SymbolConfig:
    """
    Return a copy of SymbolConfig with parameters modulated by L-system recursion depth.
    Deeper (later-generated) symbols: denser IOI (higher rate / smaller scale),
    wider pitch range (larger std or range).
    """
    if base.gesture is not None:
        return base  # a specified gesture is reproduced exactly, at any depth

    depth_frac = generation / max(1, max_generation)  # 0 .. 1
    # Denser IOI: scale down mean/scale so events are closer (higher λ for exponential)
    ioi_factor = 1.0 - k_ioi * depth_frac  # < 1 → denser
    # Wider pitch: scale up std or range
    pitch_factor = 1.0 + k_pitch * depth_frac  # > 1 → wider

    ioi_params = dict(base.ioi_dist.params)
    if base.ioi_dist.dist_type == "exponential":
        ioi_params["scale"] = max(0.005, ioi_params["scale"] * ioi_factor)
    elif base.ioi_dist.dist_type == "constant":
        ioi_params["value"] = max(0.01, ioi_params["value"] * ioi_factor)
    elif base.ioi_dist.dist_type == "uniform":
        span = ioi_params["high"] - ioi_params["low"]
        mid = (ioi_params["low"] + ioi_params["high"]) / 2
        ioi_params["low"] = max(0.01, mid - span * ioi_factor / 2)
        ioi_params["high"] = mid + span * ioi_factor / 2

    pitch_params = dict(base.pitch_dist.params)
    if base.pitch_dist.dist_type == "gaussian":
        pitch_params["std"] = min(24, pitch_params["std"] * pitch_factor)
    elif base.pitch_dist.dist_type == "uniform":
        span = pitch_params["high"] - pitch_params["low"]
        mid = (pitch_params["low"] + pitch_params["high"]) / 2
        half = min(48, span * pitch_factor / 2)
        pitch_params["low"] = int(np.clip(mid - half, 21, 107))
        pitch_params["high"] = int(np.clip(mid + half, 22, 108))

    return SymbolConfig(
        tempo_ratios=base.tempo_ratios,
        duration=base.duration,
        ioi_dist=DistributionConfig(base.ioi_dist.dist_type, ioi_params),
        pitch_dist=DistributionConfig(base.pitch_dist.dist_type, pitch_params),
        velocity_dist=base.velocity_dist,
        pitch_set=base.pitch_set,
        mode=base.mode,
    )


def sample_distribution(config: DistributionConfig) -> float:
    """Sample a value from the specified distribution."""
    if config.dist_type == 'constant':
        return config.params['value']
    elif config.dist_type == 'uniform':
        return np.random.uniform(config.params['low'], config.params['high'])
    elif config.dist_type == 'gaussian':
        return np.random.normal(config.params['mean'], config.params['std'])
    elif config.dist_type == 'exponential':
        return np.random.exponential(config.params['scale'])
    else:
        raise ValueError(f"Unknown distribution type: {config.dist_type}")

# =============================================================================
# LAYER 3: NANCARROW-XENAKIS EVENT GENERATION
# =============================================================================

def generate_section_events(
    symbol_config: SymbolConfig,
    start_time: float,
    voices: int
) -> List[Dict]:
    """Generate events for a single section using distribution-switching."""
    if symbol_config.gesture is not None:
        return generate_gesture_events(symbol_config, start_time)
    events = []
    end_time = start_time + symbol_config.duration
    
    for voice_id in range(voices):
        tempo_ratio = symbol_config.tempo_ratios[voice_id % len(symbol_config.tempo_ratios)]
        
        # Generate events for this voice
        current_time = start_time
        while current_time < end_time:
            # Sample IOI (Inter-Onset Interval)
            base_ioi = sample_distribution(symbol_config.ioi_dist)
            ioi = max(0.01, base_ioi / tempo_ratio)  # Scale by tempo ratio
            
            # Sample pitch
            raw_pitch = sample_distribution(symbol_config.pitch_dist)
            pitch = int(np.clip(raw_pitch, 21, 108))  # Piano range A0 to C8
            
            # Apply pitch set constraint if specified
            if symbol_config.pitch_set is not None:
                pitch_class = pitch % 12
                if pitch_class not in symbol_config.pitch_set:
                    # Snap to nearest pitch class in set
                    distances = [min(abs(pitch_class - pc), 12 - abs(pitch_class - pc)) 
                                 for pc in symbol_config.pitch_set]
                    nearest_pc = symbol_config.pitch_set[np.argmin(distances)]
                    pitch = (pitch // 12) * 12 + nearest_pc
                    pitch = int(np.clip(pitch, 21, 108))
            
            # Sample velocity (convert to 0-127 MIDI standard)
            raw_velocity = sample_distribution(symbol_config.velocity_dist)
            # Map from 0-1023 (Disklavier) to 0-127 (standard MIDI)
            velocity = int(np.clip(raw_velocity / 8, 1, 127))
            
            # Add voice-specific pitch offset for separation
            if symbol_config.mode == 'melodic':
                # Separate voices by register
                voice_offset = (voice_id - voices // 2) * 12
                pitch = int(np.clip(pitch + voice_offset, 21, 108))
            
            events.append({
                'onset_time': current_time,
                'pitch': pitch,
                'velocity': velocity,
                'voice_id': voice_id,
                'duration': ioi * 0.9,  # Note duration slightly less than IOI
                # Layer-2 samples, retained so that the per-layer degradation
                # analysis can compare intended against realized distributions.
                'base_ioi': base_ioi,
                'raw_pitch': float(raw_pitch),
                'raw_velocity': float(raw_velocity),
                'tempo_ratio': float(tempo_ratio),
            })
            
            current_time += ioi
    
    return events

def generate_gesture_events(symbol_config: SymbolConfig, start_time: float) -> List[Dict]:
    """Build a section from a specified gesture rather than from per-voice sampling.

    The beyond-human demonstration is written against three physical limits, and each is a
    specification, not a distribution:

      'chords'   a simultaneity of `chord_size` distinct keys every `ioi` seconds
      'trill'    one note every `ioi` seconds, cycling over `keys` adjacent keys, so that the
                 aggregate rate can exceed what a single key allows (per-key rate = rate / keys)
      'arpeggio' one note every `ioi` seconds, in repeated ascending sweeps of low..high

    Parameters come from ioi_dist.params ('value' = ioi) and pitch_dist.params.
    """
    ioi = symbol_config.ioi_dist.params['value']
    pp = symbol_config.pitch_dist.params
    end_time = start_time + symbol_config.duration
    events = []

    def add(t, pitch, voice_id):
        raw_velocity = sample_distribution(symbol_config.velocity_dist)
        events.append({
            'onset_time': t, 'pitch': int(pitch),
            'velocity': int(np.clip(raw_velocity / 8, 1, 127)),
            'voice_id': voice_id, 'duration': ioi * 0.9,
            'base_ioi': ioi, 'raw_pitch': float(pitch),
            'raw_velocity': float(raw_velocity), 'tempo_ratio': 1.0,
        })

    n_steps = int(round(symbol_config.duration / ioi))
    if symbol_config.gesture == 'chords':
        keys = np.arange(pp['low'], pp['high'] + 1)
        for k in range(n_steps):
            chord = np.sort(np.random.choice(keys, size=pp['chord_size'], replace=False))
            for j, pitch in enumerate(chord):
                add(start_time + k * ioi, pitch, j % 4)
    elif symbol_config.gesture == 'trill':
        cycle = [pp['base'] + j for j in range(pp['keys'])]
        for k in range(n_steps):
            add(start_time + k * ioi, cycle[k % len(cycle)], k % len(cycle))
    elif symbol_config.gesture == 'arpeggio':
        # Repeated ascending sweeps. A key recurs once per sweep, far beyond its reset time,
        # whereas an up-and-down sweep would re-strike the keys next to each turning point
        # within 50 ms.
        sweep = list(range(pp['low'], pp['high'] + 1))
        for k in range(n_steps):
            add(start_time + k * ioi, sweep[k % len(sweep)], 0)
    else:
        raise ValueError(f"Unknown gesture: {symbol_config.gesture}")
    return [e for e in events if e['onset_time'] < end_time]


# =============================================================================
# LAYER 4: HARDWARE LATENCY COMPENSATION (Disklavier)
# =============================================================================

def latency_linear(velocity_midi: int) -> float:
    """Calculate velocity-dependent latency in milliseconds."""
    # Convert MIDI velocity (0-127) to Disklavier scale (0-1023)
    velocity_dk = velocity_midi * 8
    # Linear model: 30ms at velocity=0, 10ms at velocity=1023
    return 30 - 20 * (velocity_dk / 1023)

def apply_latency_compensation(events: List[Dict]) -> List[Dict]:
    """Apply velocity-dependent latency pre-compensation."""
    compensated = []
    for event in events:
        latency_ms = latency_linear(event['velocity'])
        compensation_s = latency_ms / 1000.0
        
        compensated.append({
            **event,
            'trigger_time': event['onset_time'] - compensation_s,
            'compensation_ms': latency_ms
        })
    
    return compensated

KEY_RESET_S = 0.050  # electromechanical key reset time of the Disklavier action (~50 ms)


def apply_key_reset_mask(events: List[Dict], reset_s: float = KEY_RESET_S) -> List[Dict]:
    """Enforce the per-key reset constraint IOI_key >= reset_s.

    A key that has just been struck cannot be re-struck until its action has reset. For each
    MIDI pitch, across all voices, events are taken in trigger-time order (the time the
    solenoid is actually driven) and any trigger that falls within `reset_s` of the last
    kept trigger on the same key is suppressed. The suppressed event is dropped rather than
    merged or delayed, so the timing of every surviving event is untouched.
    """
    last_trigger = {}
    kept = []
    for event in sorted(events, key=lambda e: e['trigger_time']):
        pitch = event['pitch']
        previous = last_trigger.get(pitch)
        if previous is not None and event['trigger_time'] - previous < reset_s - 1e-9:
            continue
        last_trigger[pitch] = event['trigger_time']
        kept.append(event)
    return kept


# =============================================================================
# MIDI OUTPUT
# =============================================================================

def events_to_midi(events: List[Dict], filename: str, tempo: int = 120, 
                   title: str = "Amanous Composition"):
    """Convert event list to MIDI file."""
    # Sort events by trigger time
    sorted_events = sorted(events, key=lambda x: x.get('trigger_time', x['onset_time']))
    
    # Create MIDI file with deinterleave disabled to avoid duplicate note issues
    midi = MIDIFile(1, deinterleave=False)  # One track, no deinterleave
    track = 0
    time_offset = 0  # Start time in beats
    
    # Set tempo and track name (convert non-ASCII characters for MIDI compatibility)
    midi.addTempo(track, 0, tempo)
    # MIDI only supports ASCII/Latin-1, so transliterate or simplify title
    safe_title = title.encode('ascii', 'ignore').decode('ascii') or "Composition"
    midi.addTrackName(track, 0, safe_title)
    
    # Group events by voice to assign different channels
    voice_channels = {}
    
    # Convert events to MIDI notes
    for event in sorted_events:
        voice_id = event.get('voice_id', 0)
        # Assign channel per voice (max 15 channels, 0-15)
        if voice_id not in voice_channels:
            voice_channels[voice_id] = len(voice_channels) % 16
        channel = voice_channels[voice_id]
        
        time_seconds = event.get('trigger_time', event['onset_time'])
        # Convert seconds to beats
        time_beats = time_seconds * (tempo / 60.0)
        duration_beats = event['duration'] * (tempo / 60.0)
        
        midi.addNote(
            track=track,
            channel=channel,
            pitch=event['pitch'],
            time=max(0, time_beats),
            duration=max(0.05, duration_beats),
            volume=event['velocity']
        )
    
    # Write to file
    with open(filename, 'wb') as f:
        midi.writeFile(f)
    
    return filename

# =============================================================================
# MAIN COMPOSITION PIPELINE
# =============================================================================

def compose(
    config: CompositionConfig,
    lsystem_sequence_override: Optional[str] = None,
    apply_hw_compensation: bool = True,
) -> Tuple[List[Dict], str, str]:
    """
    Generate a complete composition using the Amanous framework.

    Optional overrides for ablation experiments:
    - lsystem_sequence_override: if provided, use this string instead of L-system expansion.
    - apply_hw_compensation: if False, skip Layer 4 entirely (trigger_time = onset_time,
      no key-reset mask), so the returned events are the raw Layer 3 stream.

    Layer 4 has two stages. Latency pre-compensation shifts each trigger earlier by L(v), and
    the key-reset mask then suppresses any trigger that would re-strike a key within 50 ms.
    
    Returns:
        Tuple of (events, lsystem_sequence, summary)
    """
    np.random.seed(config.seed)
    
    # Layer 1: L-System expansion with (symbol, generation) for depth-weighted mapping
    if lsystem_sequence_override is not None:
        expanded = [(s, 0) for s in lsystem_sequence_override]
        lsystem_sequence = lsystem_sequence_override
        max_generation = 1
    else:
        expanded = expand_lsystem(
            config.axiom,
            config.production_rules,
            config.iterations,
        )
        lsystem_sequence = "".join(s for s, _ in expanded)
        max_generation = max((g for _, g in expanded), default=1)
    
    # Layer 2 & 3: Generate events per section; Layer 2 uses depth-weighted params
    all_events = []
    current_time = 0.0
    
    for symbol, generation in expanded:
        base_config = config.symbol_configs[symbol]
        symbol_config = apply_depth_weight_to_config(
            base_config, generation, max_generation
        )
        section_events = generate_section_events(
            symbol_config,
            current_time,
            config.voices,
        )
        all_events.extend(section_events)
        current_time += symbol_config.duration
    
    # Sort by onset time
    all_events.sort(key=lambda x: x['onset_time'])
    
    # Layer 4: Hardware compensation (optional)
    if apply_hw_compensation:
        compensated_events = apply_latency_compensation(all_events)
        n_before_mask = len(compensated_events)
        compensated_events = apply_key_reset_mask(compensated_events)
        n_suppressed = n_before_mask - len(compensated_events)
        compensated_events.sort(key=lambda x: x['trigger_time'])
    else:
        n_suppressed = 0
        compensated_events = [
            {**e, 'trigger_time': e['onset_time'], 'compensation_ms': 0.0}
            for e in all_events
        ]
        compensated_events.sort(key=lambda x: x['trigger_time'])
    
    # Summary
    total_duration = max(e['onset_time'] + e['duration'] for e in all_events)
    summary = f"""
=== Amanous Composition Summary ===
Title: {config.title}
L-System Sequence: {lsystem_sequence}
Total Sections: {len(lsystem_sequence)}
Total Events: {len(compensated_events)} (Layer 3 produced {len(all_events)}; key-reset mask suppressed {n_suppressed})
Duration: {total_duration:.2f} seconds
Voices: {config.voices}
Seed: {config.seed}
"""
    
    return compensated_events, lsystem_sequence, summary

# =============================================================================
# PRESET CONFIGURATIONS
# =============================================================================

def get_canonical_config() -> CompositionConfig:
    """Get the canonical configuration from the paper (ABAABABA)."""
    
    # C Major pitch classes: C, D, E, F, G, A, B = 0, 2, 4, 5, 7, 9, 11
    c_major = [0, 2, 4, 5, 7, 9, 11]
    chromatic = list(range(12))
    
    symbol_configs = {
        'A': SymbolConfig(
            tempo_ratios=(3.0, 4.0),  # 3:4 ratio
            duration=10.0,
            ioi_dist=DistributionConfig('constant', {'value': 0.2}),  # 5 notes/s
            pitch_dist=DistributionConfig('gaussian', {'mean': 60, 'std': 8}),
            velocity_dist=DistributionConfig('constant', {'value': 640}),  # mf
            pitch_set=c_major,
            mode='melodic'
        ),
        'B': SymbolConfig(
            tempo_ratios=(1.0, np.sqrt(2)),  # 1:√2 ratio
            duration=8.0,
            ioi_dist=DistributionConfig('exponential', {'scale': 0.03}),  # ~33 notes/s
            pitch_dist=DistributionConfig('gaussian', {'mean': 60, 'std': 15}),
            velocity_dist=DistributionConfig('uniform', {'low': 400, 'high': 900}),
            pitch_set=chromatic,
            mode='textural'
        )
    }
    
    return CompositionConfig(
        axiom='A',
        production_rules={'A': 'AB', 'B': 'A'},
        iterations=4,
        symbol_configs=symbol_configs,
        voices=2,
        seed=42,
        title="Canonical ABAABABA Validation Composition"
    )

def get_beyond_human_demo_config() -> CompositionConfig:
    """Get configuration for beyond-human demonstration pieces."""
    
    chromatic = list(range(12))
    
    symbol_configs = {
        # Extreme polyphony: a 40-note simultaneity every 500 ms, drawn from the 88 keys
        'P': SymbolConfig(
            tempo_ratios=(1.0,),
            duration=10.0,
            ioi_dist=DistributionConfig('constant', {'value': 0.5}),
            pitch_dist=DistributionConfig('constant', {'low': 21, 'high': 108, 'chord_size': 40}),
            velocity_dist=DistributionConfig('gaussian', {'mean': 600, 'std': 100}),
            mode='textural', gesture='chords'
        ),
        # Repetition: a 30 Hz trill. One key resets in about 50 ms, so it cannot be re-struck
        # at 30 Hz. Alternating two adjacent keys gives 15 Hz per key (66.7 ms).
        'R': SymbolConfig(
            tempo_ratios=(1.0,),
            duration=8.0,
            ioi_dist=DistributionConfig('constant', {'value': 1 / 30}),
            pitch_dist=DistributionConfig('constant', {'base': 60, 'keys': 2}),
            velocity_dist=DistributionConfig('uniform', {'low': 500, 'high': 800}),
            mode='melodic', gesture='trill'
        ),
        # Speed and span: a six-octave arpeggio (72 semitones) at a 25 ms IOI
        'S': SymbolConfig(
            tempo_ratios=(1.0,),
            duration=8.0,
            ioi_dist=DistributionConfig('constant', {'value': 0.025}),
            pitch_dist=DistributionConfig('constant', {'low': 24, 'high': 96}),
            velocity_dist=DistributionConfig('gaussian', {'mean': 700, 'std': 50}),
            mode='textural', gesture='arpeggio'
        ),
        # Transition/rest
        'T': SymbolConfig(
            tempo_ratios=(1.0, 1.0),
            duration=4.0,
            ioi_dist=DistributionConfig('constant', {'value': 0.5}),
            pitch_dist=DistributionConfig('gaussian', {'mean': 60, 'std': 5}),
            velocity_dist=DistributionConfig('constant', {'value': 400}),
            pitch_set=[0, 4, 7],  # C major triad
            mode='melodic'
        )
    }
    
    return CompositionConfig(
        axiom='T',
        production_rules={'T': 'TPRST', 'P': 'P', 'R': 'R', 'S': 'S'},
        iterations=1,
        symbol_configs=symbol_configs,
        voices=4,
        seed=42,
        title="Beyond-Human-Density"
    )

def get_convergence_point_config() -> CompositionConfig:
    """Get configuration demonstrating Convergence Point Calculus."""
    
    c_major = [0, 2, 4, 5, 7, 9, 11]
    chromatic = list(range(12))
    
    # Pre-convergence: sparse, melodic
    pre_cp = SymbolConfig(
        tempo_ratios=(3.0, 4.0),  # 3:4 ratio → converges at t=12τ
        duration=15.0,  # Build up to convergence
        ioi_dist=DistributionConfig('constant', {'value': 0.2}),
        pitch_dist=DistributionConfig('gaussian', {'mean': 60, 'std': 6}),
        velocity_dist=DistributionConfig('constant', {'value': 500}),
        pitch_set=c_major,
        mode='melodic'
    )
    
    # Post-convergence: dense, textural
    post_cp = SymbolConfig(
        tempo_ratios=(3.0, 4.0),
        duration=15.0,
        ioi_dist=DistributionConfig('exponential', {'scale': 0.02}),
        pitch_dist=DistributionConfig('gaussian', {'mean': 60, 'std': 18}),
        velocity_dist=DistributionConfig('uniform', {'low': 300, 'high': 1000}),
        pitch_set=chromatic,
        mode='textural'
    )
    
    return CompositionConfig(
        axiom='C',
        production_rules={'C': 'CD', 'D': 'D'},
        iterations=1,
        symbol_configs={'C': pre_cp, 'D': post_cp},
        voices=2,
        seed=42,
        title="Convergence Point (3:4 Canon)"
    )

# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Amanous Algorithmic Composer")
    parser.add_argument('--preset', type=str, default='canonical',
                       choices=['canonical', 'beyond_human', 'convergence'],
                       help='Preset configuration to use')
    parser.add_argument('--output', type=str, default='composition.mid',
                       help='Output MIDI filename')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed for reproducibility')
    parser.add_argument('--tempo', type=int, default=120,
                       help='MIDI tempo in BPM')
    
    args = parser.parse_args()
    
    # Select configuration
    if args.preset == 'canonical':
        config = get_canonical_config()
    elif args.preset == 'beyond_human':
        config = get_beyond_human_demo_config()
    elif args.preset == 'convergence':
        config = get_convergence_point_config()
    
    config.seed = args.seed
    
    print("=" * 70)
    print("AMANOUS: Unified Parametric Framework for Algorithmic Piano Composition")
    print("=" * 70)
    
    # Generate composition
    events, sequence, summary = compose(config)
    print(summary)
    
    # Export to MIDI
    midi_file = args.output
    events_to_midi(events, midi_file, tempo=args.tempo, title=config.title)
    print(f"MIDI file saved: {midi_file}")
    
    # Also save events to CSV
    import pandas as pd
    csv_file = midi_file.replace('.mid', '_events.csv')
    df = pd.DataFrame(events)
    df.to_csv(csv_file, index=False)
    print(f"Events CSV saved: {csv_file}")
    
    print("\n" + "=" * 70)
    print("First 15 events:")
    print("-" * 70)
    for i, e in enumerate(events[:15]):
        print(f"{i:3d}: t={e['trigger_time']:.4f}s  pitch={e['pitch']:3d}  "
              f"vel={e['velocity']:3d}  voice={e['voice_id']}  "
              f"comp={e['compensation_ms']:.1f}ms")
