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
  // Work after the paper (code/amanous_v2.py). Not part of the published article.
  'v2_study_1',
  'v2_study_2',
];

// Titles aligned with the paper's Supplementary Materials appendix (Excerpts 1-4)
export const TRACKS = {
  canonical_abaababa: {
    title: 'Canonical ABAABABA Validation Composition',
    style: 'L-system & 3:4 tempo canon',
    description: 'L-system macro-form with deterministic (A) and textural (B) sections; 3:4 tempo canon (paper Excerpt 3). This is the run analysed in the paper (seed 42).',
    duration: '74s',
    highlight: '6,031 events; C major vs chromatic sections',
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
  v2_study_1: {
    title: 'After the paper: Study 1 (Canon 3:4)',
    style: 'Amanous v2 · motivic tempo canon and swelling clouds',
    description: 'Not part of the published article. One motif stated by two voices at 3:4, transformed from statement to statement, against stochastic clouds that walk inside the harmony. C lydian, form ABAABABA, sustain pedal changed with the chords.',
    duration: '74s',
    highlight: 'Same four layers; Layer 3 now has melodic memory, harmony, rests and dynamic arcs',
  },
  v2_study_2: {
    title: 'After the paper: Study 2 (Canon 4:5:6)',
    style: 'Amanous v2 · three-voice tempo canon',
    description: 'Not part of the published article. Three voices at 4:5:6 in D dorian over thirteen shorter sections, with sections differing in derivation depth.',
    duration: '79s',
    highlight: 'Voices converge at every section boundary',
  },
};
