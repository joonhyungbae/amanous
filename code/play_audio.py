#!/usr/bin/env python3
"""
Amanous Audio Player
====================

Simple audio player for generated compositions.
"""

import os
import sys
import subprocess
from pathlib import Path

from config import AUDIO_DIR  # Salamander Grand Piano HQ renders; override with AMANOUS_AUDIO_DIR

# Aligned with the paper's Supplementary Materials appendix (Excerpts 1-4, section order)
DESCRIPTIONS = {
    "canonical_abaababa": {
        "title": "Canonical ABAABABA Validation Composition",
        "style": "L-system & 3:4 tempo canon",
        "description": "L-system macro-form with deterministic (A) and textural (B) sections; 3:4 tempo canon (Excerpt 3).",
        "duration": "74s",
        "highlight": "3:4 tempo canon, C major vs chromatic"
    },
    "beyond_human_demo": {
        "title": "Beyond-Human-Density",
        "style": "Superhuman piano textures",
        "description": "40-note chords, 30 Hz multi-key trill, 6-octave arpeggio (Excerpt 1).",
        "duration": "34s",
        "highlight": "Three sections, each past a different physical limit of human performance"
    },
    "minimalist_phase": {
        "title": "Phase Music — Minimalist Study",
        "style": "Phase-shift · pentatonic",
        "description": "Reich-inspired phase-shift; pentatonic set, 1:1.01 tempo drift (Excerpt 2).",
        "duration": "80s",
        "highlight": "Deterministic scaffolding with minimal stochastic variation"
    },
    "convergence_point": {
        "title": "Convergence Point (3:4 Canon)",
        "style": "3:4 tempo canon · texture switch",
        "description": "Pre-CP sparse/melodic and post-CP dense/textural switch at t = 15 s (Excerpt 4).",
        "duration": "30s",
        "highlight": "Density and tonality shift at convergence"
    }
}

def get_player_command():
    """Find an available audio player."""
    players = [
        ['paplay'],                    # PulseAudio
        ['aplay', '-q'],               # ALSA
        ['ffplay', '-nodisp', '-autoexit'],  # FFmpeg
        ['play'],                      # SoX
    ]

    for player in players:
        try:
            subprocess.run(['which', player[0]], capture_output=True, check=True)
            return player
        except:
            continue

    return None

def play_audio(filepath: str, player_cmd: list = None):
    """Play an audio file."""
    if player_cmd is None:
        player_cmd = get_player_command()

    if player_cmd is None:
        print("No audio player found.")
        print("Install one of: pulseaudio, alsa-utils, ffmpeg, sox")
        return False

    cmd = player_cmd + [str(filepath)]

    try:
        print(f"\n▶ Playing... (Ctrl+C to stop)")
        subprocess.run(cmd)
        return True
    except KeyboardInterrupt:
        print("\n⏹ Stopped")
        return True
    except Exception as e:
        print(f"Playback error: {e}")
        return False

def list_compositions():
    """List available compositions."""
    print("\n" + "=" * 70)
    print("🎹 AMANOUS - Algorithmic composition audio library")
    print("=" * 70)

    wav_files = sorted(AUDIO_DIR.glob("*.wav"))

    if not wav_files:
        print("No audio files found. Convert MIDI first.")
        return []

    print(f"\n{'No':<4} {'Filename':<25} {'Length':<8} {'Style'}")
    print("-" * 70)

    for i, wav in enumerate(wav_files, 1):
        name = wav.stem
        info = DESCRIPTIONS.get(name, {})
        duration = info.get('duration', '??')
        style = info.get('style', '')
        print(f"{i:<4} {name:<25} {duration:<8} {style}")

    return wav_files

def show_composition_info(name: str):
    """Show composition details."""
    info = DESCRIPTIONS.get(name)

    if info:
        print(f"\n{'─' * 50}")
        print(f"🎵 {info['title']}")
        print(f"{'─' * 50}")
        print(f"Style: {info['style']}")
        print(f"Duration: {info['duration']}")
        print(f"\n{info['description']}")
        print(f"\n💡 Highlight: {info['highlight']}")
        print(f"{'─' * 50}")

def interactive_player():
    """Interactive player loop."""
    wav_files = list_compositions()

    if not wav_files:
        return

    player_cmd = get_player_command()

    print("\nUsage:")
    print("  number: play that composition")
    print("  'i number': show composition info")
    print("  'a': play all")
    print("  'q': quit")
    print()

    while True:
        try:
            choice = input("Choice> ").strip().lower()

            if choice == 'q':
                print("Quitting.")
                break

            if choice == 'a':
                print("\nPlaying all compositions in order...")
                for wav in wav_files:
                    show_composition_info(wav.stem)
                    play_audio(wav, player_cmd)
                continue

            if choice.startswith('i '):
                try:
                    idx = int(choice[2:]) - 1
                    if 0 <= idx < len(wav_files):
                        show_composition_info(wav_files[idx].stem)
                except ValueError:
                    print("Invalid input.")
                continue

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(wav_files):
                    wav = wav_files[idx]
                    show_composition_info(wav.stem)
                    play_audio(wav, player_cmd)
                else:
                    print(f"Enter a number between 1 and {len(wav_files)}.")
            except ValueError:
                print("Invalid input. Enter a number.")

        except KeyboardInterrupt:
            print("\nQuitting.")
            break

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Amanous Audio Player")
    parser.add_argument('file', nargs='?', help='WAV file to play')
    parser.add_argument('--list', '-l', action='store_true', help='List compositions')
    parser.add_argument('--all', '-a', action='store_true', help='Play all')

    args = parser.parse_args()

    if args.list:
        list_compositions()
    elif args.all:
        wav_files = list_compositions()
        player_cmd = get_player_command()
        for wav in wav_files:
            show_composition_info(wav.stem)
            play_audio(wav, player_cmd)
    elif args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            filepath = AUDIO_DIR / args.file
            if not filepath.exists():
                filepath = AUDIO_DIR / f"{args.file}.wav"

        if filepath.exists():
            show_composition_info(filepath.stem)
            play_audio(filepath)
        else:
            print(f"File not found: {args.file}")
    else:
        interactive_player()
