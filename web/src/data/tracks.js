/**
 * Composition metadata (aligned with code/play_audio.py DESCRIPTIONS).
 * Order follows the paper: Section 4.1.6 (Canonical, Beyond-human, Phase Music), then Section 4.4 (Convergence Point).
 * All audio is a software render of the generated MIDI (FluidSynth, Salamander Grand Piano soundfont), not a recording of a Disklavier.
 * Audio URL: {BASE_URL}audio/{id}.wav
 */
export const TRACK_ORDER = [
  'canonical_abaababa',   // Excerpt 3 (Section 4.1.6)
  'beyond_human_demo',    // Excerpt 1 (Section 4.1.6)
  'minimalist_phase',    // Excerpt 2 (Section 4.1.6)
  'convergence_point',   // Excerpt 4 (Section 4.4)
];

// Titles aligned with the paper's Supplementary Materials appendix (Excerpts 1-4)
export const TRACKS = {
  canonical_abaababa: {
    title: 'Canonical ABAABABA Validation Composition',
    style: 'L-system & 3:4 tempo canon',
    description: 'L-system macro-form with deterministic (A) and textural (B) sections; 3:4 tempo canon (paper Excerpt 3). This is the run analysed in the paper (seed 42).',
    duration: '74s',
    highlight: '6,591 events; C major vs chromatic sections',
  },
  beyond_human_demo: {
    title: 'Beyond-Human-Density',
    style: 'Superhuman piano textures',
    description: 'Polyphony (40-note chords), 30 Hz multi-key trill, 6-octave arpeggio (paper Excerpt 1).',
    duration: '34s',
    highlight: 'Three sections, each past a different physical limit of human performance',
  },
  minimalist_phase: {
    title: 'Phase Music — Minimalist Study',
    style: 'Phase-shift · pentatonic',
    description: 'Reich-inspired phase-shift; pentatonic set, 1:1.01 tempo drift between voices (paper Excerpt 2).',
    duration: '80s',
    highlight: 'Deterministic scaffolding with minimal stochastic variation',
  },
  convergence_point: {
    title: 'Convergence Point (3:4 Canon)',
    style: '3:4 tempo canon · texture switch',
    description: 'Pre-CP sparse/melodic and post-CP dense/textural switch at t = 15 s (paper Excerpt 4).',
    duration: '30s',
    highlight: 'Density and tonality shift at convergence',
  },
};
