#!/usr/bin/env python3
"""
MIDI to Audio Converter for Amanous
===================================

Converts MIDI files to high-quality audio using FluidSynth.
Uses FluidR3 GM Grand Piano by default.
"""

import subprocess
import os
import sys
from pathlib import Path

import config

# Soundfont search order, resolved centrally (see config.py). Salamander Grand Piano
# (Yamaha C5, Disklavier-like) is preferred, then system GM soundfonts.
DEFAULT_SOUNDFONTS = [str(p) for p in config.soundfont_candidates()]

def find_soundfont():
    """Find an available soundfont."""
    found = config.find_soundfont()
    return str(found) if found else None

def midi_to_wav(midi_path: str, output_path: str = None, 
                soundfont: str = None, sample_rate: int = 44100,
                gain: float = 1.0) -> str:
    """
    Convert MIDI to WAV using FluidSynth.

    Parameters
    ----------
    midi_path : str
        Input MIDI file path
    output_path : str, optional
        Output WAV path (default: same name .wav)
    soundfont : str, optional
        Soundfont path
    sample_rate : int
        Sample rate (default: 44100 Hz)
    gain : float
        Gain/volume (default: 1.0)

    Returns
    -------
    str
        Path to generated WAV file
    """
    midi_path = Path(midi_path)
    
    if not midi_path.exists():
        raise FileNotFoundError(f"MIDI file not found: {midi_path}")
    
    if output_path is None:
        output_path = midi_path.with_suffix('.wav')
    else:
        output_path = Path(output_path)
    
    if soundfont is None:
        soundfont = find_soundfont()
        if soundfont is None:
            raise FileNotFoundError("Soundfont not found. Use --soundfont option.")
    
    # Build FluidSynth command
    cmd = [
        'fluidsynth',
        '-ni',                          # No interactive mode
        '-g', str(gain),                # Gain
        '-r', str(sample_rate),         # Sample rate
        '-F', str(output_path),         # Output file
        soundfont,                      # Soundfont
        str(midi_path)                  # MIDI file
    ]
    
    print(f"Converting: {midi_path.name} → {output_path.name}")
    print(f"Soundfont: {soundfont}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            raise RuntimeError(f"FluidSynth conversion failed: {result.stderr}")
        
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"✓ Done: {output_path} ({size_mb:.2f} MB)")
            return str(output_path)
        else:
            raise RuntimeError("Output file was not created.")

    except subprocess.TimeoutExpired:
        raise RuntimeError("Conversion timeout (5 min)")

def wav_to_mp3(wav_path: str, output_path: str = None, 
               bitrate: str = "320k") -> str:
    """
    Convert WAV to MP3 (using ffmpeg).

    Parameters
    ----------
    wav_path : str
        Input WAV file path
    output_path : str, optional
        Output MP3 file path
    bitrate : str
        Bitrate (default: 320k)

    Returns
    -------
    str
        Path to generated MP3 file
    """
    wav_path = Path(wav_path)
    
    if output_path is None:
        output_path = wav_path.with_suffix('.mp3')
    else:
        output_path = Path(output_path)
    
    cmd = [
        'ffmpeg', '-y',
        '-i', str(wav_path),
        '-codec:a', 'libmp3lame',
        '-b:a', bitrate,
        str(output_path)
    ]
    
    print(f"Converting to MP3: {wav_path.name} → {output_path.name}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"✓ MP3 done: {output_path} ({size_mb:.2f} MB)")
            return str(output_path)
        else:
            print(f"Warning: MP3 conversion failed, using WAV")
            return str(wav_path)
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("Warning: ffmpeg not found or timeout, using WAV")
        return str(wav_path)

def convert_midi(midi_path: str, output_dir: str = None,
                 format: str = "wav", soundfont: str = None,
                 gain: float = 1.0) -> str:
    """
    Convert MIDI file to audio (main entry).

    Parameters
    ----------
    midi_path : str
        Input MIDI file path
    output_dir : str, optional
        Output directory (default: same as MIDI file)
    format : str
        Output format ('wav' or 'mp3')
    soundfont : str, optional
        Soundfont path

    Returns
    -------
    str
        Path to generated audio file
    """
    midi_path = Path(midi_path)
    
    if output_dir is None:
        output_dir = midi_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    wav_path = output_dir / f"{midi_path.stem}.wav"
    
    # MIDI → WAV
    wav_file = midi_to_wav(midi_path, wav_path, soundfont, gain=gain)
    
    # WAV → MP3 if requested
    if format.lower() == 'mp3':
        mp3_path = output_dir / f"{midi_path.stem}.mp3"
        return wav_to_mp3(wav_file, mp3_path)
    
    return wav_file

def batch_convert(input_dir: str, output_dir: str = None,
                  format: str = "wav", soundfont: str = None):
    """
    Batch convert all MIDI files in a directory.
    """
    input_dir = Path(input_dir)
    midi_files = list(input_dir.glob("*.mid")) + list(input_dir.glob("*.midi"))
    
    if not midi_files:
        print(f"No MIDI files found in: {input_dir}")
        return []
    
    print(f"\nFound {len(midi_files)} MIDI file(s)")
    print("=" * 50)
    
    results = []
    for midi_file in midi_files:
        try:
            audio_file = convert_midi(midi_file, output_dir, format, soundfont)
            results.append(audio_file)
            print()
        except Exception as e:
            print(f"✗ Failed: {midi_file.name} - {e}\n")
    
    return results

# Default output: web demo path (served on deploy); override with AMANOUS_OUTPUT_DIR
DEFAULT_OUTPUT_DIR = config.OUTPUT_DIR

# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Amanous MIDI to Audio Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single file (default: save to web/public/audio/)
  python midi_to_audio.py composition.mid

  # Output MP3
  python midi_to_audio.py composition.mid --format mp3

  # Batch convert (default: web/public/audio/)
  python midi_to_audio.py --batch ./compositions/

  # Custom output dir
  python midi_to_audio.py composition.mid -o ./audio_hq
  python midi_to_audio.py --batch ./compositions/ -o ./audio_hq

  # Custom soundfont
  python midi_to_audio.py composition.mid --soundfont ~/piano.sf2
"""
    )
    
    parser.add_argument('input', nargs='?', help='MIDI file path')
    parser.add_argument('--batch', type=str, help='Directory to batch convert')
    parser.add_argument('--output', '-o', type=str,
                       help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})')
    parser.add_argument('--format', '-f', type=str, default='wav',
                       choices=['wav', 'mp3'], help='Output format')
    parser.add_argument('--soundfont', '-s', type=str, help='Soundfont path')
    parser.add_argument('--gain', '-g', type=float, default=1.0,
                        help='FluidSynth gain. Dense or pedalled pieces clip at 1.0; try 0.35 and normalise afterwards')
    parser.add_argument('--list-sf', action='store_true', help='List available soundfonts')
    
    args = parser.parse_args()
    
    if args.list_sf:
        print("Available soundfonts:")
        for sf in DEFAULT_SOUNDFONTS:
            exists = "✓" if os.path.exists(sf) else "✗"
            print(f"  {exists} {sf}")
        sys.exit(0)
    
    output_dir = args.output if args.output is not None else str(DEFAULT_OUTPUT_DIR)
    
    if args.batch:
        results = batch_convert(args.batch, output_dir, args.format, args.soundfont)
        print(f"\nDone: {len(results)} file(s) converted")
    elif args.input:
        result = convert_midi(args.input, output_dir, args.format, args.soundfont, gain=args.gain)
        print(f"\nResult: {result}")
    else:
        parser.print_help()
