# Amanous

**Distribution-switching for superhuman piano density on Yamaha Disklavier.**

Amanous is a hardware-aware algorithmic composition system that unifies **L-systems**, **tempo canons**, and **stochastic distributions** in a single pipeline. It generates piano music at note densities, polyphony, and register spans beyond human performance limits, while respecting the Disklavier’s actuation constraints.

- **Listen to the excerpts:** [joonhyungbae.github.io/amanous](https://joonhyungbae.github.io/amanous/)
- **Paper:** *Amanous: Distribution-Switching for Superhuman Piano Density on Disklavier* (JCMS)

---

## Features

- **Hierarchical distribution-switching** — L-system symbols select distinct distributional regimes (not just parameter tweaks), producing statistically separable sections with large effect sizes.
- **Hardware abstraction layer (HAL)** — Velocity-dependent latency and key-reset limits are formalized and compensated so that superhuman textures stay within the instrument’s actuable envelope.
- **Operational envelope across density** — Structured and random textures are most separable near 25 notes/s, and single-domain melodic metrics lose that separability over the 40–100 notes/s band. No sharp threshold is claimed. Above the band, distributional content rather than melodic order carries the difference.
- **Convergence point calculus** — Tempo-canon convergence events drive distribution switches, linking macro temporal structure to micro-level texture.

All results are computational (MIDI and statistical). Nothing here was measured on a physical instrument: the latency model is a stated prior to be calibrated per Disklavier, and the audio excerpts are software renders of the generated MIDI (FluidSynth with a Salamander Grand Piano soundfont). Psychoacoustic validation is proposed for future work.

---

## Project structure

| Path | Description |
|------|-------------|
| `code/` | Main composition pipeline: `amanous_composer.py`, ablations, MIDI→audio, analysis |
| `supplementary_code/` | Experiments, RQ validations, coherence metrics, HAL and latency robustness |
| `compositions/` | Example composition data (event CSVs; MIDI/WAV when generated) |
| `audio_hq/` | High-quality WAV renders of selected compositions |
| `web/` | React + Vite player for the four excerpts, published with GitHub Pages |
| `amanous_paper/` | LaTeX manuscript (JCMS), kept in its own repository: [amanous_paper](https://github.com/joonhyungbae/amanous_paper) |

---

## Getting started

### Python (composition and analysis)

Core pipeline and supplementary code use Python 3.

```bash
# From repo root
pip install -r supplementary_code/requirements.txt
# Or for code/ only: numpy scipy pandas midiutil
```

Run the main composer (example):

```bash
cd code
python amanous_composer.py   # or use custom_composition.py for custom configs
```

Ablations and experiments live under `supplementary_code/` (see `experiments/`, `rq1_distribution_switching/`, etc.). Check individual scripts for usage.

### Reproducing the paper

Everything uses fixed seeds (42 unless stated). Run from `code/`.

| Paper result | Source |
|---|---|
| Canonical run (6,591 events), Tables 3–5: densities, MC/RC/PCC, per-layer KS degradation | `python analyze_canonical.py` → `canonical_analysis.json` |
| Excerpt 3 MIDI and events (the same run) | `python amanous_composer.py --preset canonical --seed 42` |
| Density sweep, Figure 3: peak separability at 25 notes/s, 40–100 notes/s loss band | `python discriminability_analysis.py` → `discriminability_analysis.json` |
| Window-sensitivity check, flat single-voice-coherence curve | `perceptual_saturation_wsweep.py`, `density_sweep_breakpoint.py` |
| Ablations (a)–(c), Table 9 | `python run_all_ablations.py` → `ablation_*.json` |
| Continuous convergence-point tracking (r = .928) | `python cp_continuous_tracking.py` |
| L-system redundancy/LZ and recurrence (Tables 7–8, Figure 2) | `supplementary_code/experiments/lsystem_information_analysis.py`, `visualize_recurrence.py` |
| ε sensitivity (Table 19, Figure 5) | `supplementary_code/experiments/epsilon_sensitivity_cp.py`, `epsilon_sensitivity_full_sweep.py` |
| Latency mismatch and exponent sensitivity (Appendices C–D, Figure 4) | `supplementary_code/experiments/latency_mismatch_simulation.py`, `latency_sensitivity_test.py`, `sensitivity_analysis_layer4_cp.py` |

Some statistics are reported from saved outputs under `supplementary_code/data/csv/` rather than from a script in this repository:

| Paper result | Saved output |
|---|---|
| Discrete convergence-point switch, Table 12 (60 s run, switch at 30 s, stochastic voice, one-second windows) | `composition_event_driven_switch.csv` |
| Compensation results, Table 10, and the robustness-filter SD | `correction_pipeline_validation_results.csv`, `note_by_note_error_analysis.csv`, `latency_filter_effectiveness_comparison.csv` |
| Cross-domain constraints, Table 11 | `chord_generator_summary_stats.csv`, `chord_generator_statistical_tests.csv`, `wvss_comparison_results.csv` |
| Pitch–velocity coupling | `pitch_velocity_coupling_results.csv` |
| Constraint-application efficiency | `chained_reactive_constraint_results.csv` |

**Retired material.** An earlier draft claimed a sharp coherence-saturation threshold and a distribution-independence experiment. Both were withdrawn during review and are not results of the paper. `code/breakpoint_bootstrap.py` and `code/recalculate_statistics.py` are tombstones, and `supplementary_code/experiments/density_sweep_null_model_comparison.py` (with its `--distribution-independence` mode and figure), `threshold_analysis.py`, `supplementary_code/rq3_coherence_thresholds/validate_breakpoints.py`, and `supplementary_code/data/csv/psychoacoustic_thresholds.csv` are kept for the record only. `code/canonical_symbol_only_control.*` is the 3,555-event control with recursion-depth modulation disabled, used by the ablations; it is not Excerpt 3.

### Paths and configuration

All filesystem locations are resolved in one place, `code/config.py`, relative to the repository root, so a fresh clone runs without editing any source file. Override any location with an environment variable when your layout differs:

| Variable | Default | Purpose |
|----------|---------|---------|
| `AMANOUS_ROOT` | parent of `code/` | Repository root |
| `AMANOUS_AUDIO_DIR` | `audio_hq/` | High-quality WAV renders |
| `AMANOUS_SOUNDFONT_DIR` | `soundfonts/` | SoundFont search directory |
| `AMANOUS_SOUNDFONT` | (unset) | Explicit `.sf2` file, wins over the search list |
| `AMANOUS_OUTPUT_DIR` | `web/public/audio/` | Rendered audio for the web app |
| `AMANOUS_CODE_EXTRACTED` | `code_extracted/` | Legacy; read only by a deprecated script |

```bash
AMANOUS_AUDIO_DIR=/mnt/renders python play_audio.py
```

### SoundFonts (MIDI → WAV)

SoundFont files (`.sf2`) are **not** in the repo (large binaries; see `.gitignore`). To convert MIDI to WAV you need either a system GM soundfont or a piano soundfont in `soundfonts/`.

**Option A — Quick start (Linux):** Install FluidSynth and the GM soundfont; the pipeline will use it automatically.

```bash
sudo apt install -y fluidsynth fluid-soundfont-gm
```

**Option B — Better piano quality:** Use the Salamander Grand Piano (Yamaha C5, Disklavier-like). Run the setup script, then download and place the `.sf2` as instructed:

```bash
cd code
python download_soundfont.py
# Follow the printed links; put the .sf2 in repo root's soundfonts/ as SalamanderGrandPiano.sf2 or SalamanderC5-Lite.sf2
```

Optional: `python download_soundfont.py --download-salamander` attempts an automatic download (Google Drive may require manual confirmation). Check available soundfonts: `python midi_to_audio.py --list-sf`.

### Web (listen to excerpts)

```bash
./dev.sh      # local dev server at http://localhost:5173
./deploy.sh   # build and publish to the gh-pages branch (GitHub Pages)
```

Place WAV files in `web/public/audio/` (e.g. `canonical_abaababa.wav`, `convergence_point.wav`) so the player can load them. Track list and descriptions are in `web/src/data/tracks.js`.


## License

This project is licensed under **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**. You may share and adapt the material for non-commercial use with attribution. See [LICENSE](LICENSE) for the full text.
