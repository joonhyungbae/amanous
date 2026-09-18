"""
RETIRED -- kept for the record only; not a source for the published paper.

An earlier draft claimed a sharp coherence-saturation threshold and a
distribution-independence experiment. Both were withdrawn during review. The
paper's density result comes from code/discriminability_analysis.py. See the
"Reproducing the paper" section of the README.
"""
"""
RQ3 Validation: Coherence Threshold Breakpoints

Validates the metric-derived density breakpoints (Section 7):
- Melodic coherence breakpoint: 30 notes/s
- Tonal stability breakpoint: 24.2 notes/s
- SSR reduction: 90.2%
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))

import pandas as pd
import numpy as np
from scipy import stats


def validate_melodic_breakpoint(coherence_path):
    """
    Validate melodic coherence breakpoint using piecewise regression.
    
    Expected: Breakpoint at 30 notes/s, 90.2% SSR reduction
    """
    df = pd.read_csv(coherence_path)
    
    density = df['density'].values
    coherence = df['melodic_coherence'].values
    
    # Test breakpoints
    best_bp = None
    best_ssr_reduction = 0
    
    for bp in range(20, 50, 2):
        pre = density <= bp
        post = density > bp
        
        if sum(pre) < 2 or sum(post) < 2:
            continue
        
        # Piecewise fit
        slope_pre, _, _, _, _ = stats.linregress(density[pre], coherence[pre])
        slope_post, _, _, _, _ = stats.linregress(density[post], coherence[post])
        
        # Simple linear fit
        slope_all, intercept_all, _, _, _ = stats.linregress(density, coherence)
        
        # Calculate SSR
        pred_all = slope_all * density + intercept_all
        ssr_linear = np.sum((coherence - pred_all)**2)
        
        pred_pre = slope_pre * density[pre] + np.mean(coherence[pre] - slope_pre * density[pre])
        pred_post = slope_post * density[post] + np.mean(coherence[post] - slope_post * density[post])
        
        ssr_piecewise = (np.sum((coherence[pre] - pred_pre)**2) + 
                         np.sum((coherence[post] - pred_post)**2))
        
        reduction = (ssr_linear - ssr_piecewise) / ssr_linear * 100
        
        if reduction > best_ssr_reduction:
            best_ssr_reduction = reduction
            best_bp = bp
            best_slope_ratio = abs(slope_pre / slope_post) if slope_post != 0 else np.inf
    
    return {
        'breakpoint': best_bp,
        'ssr_reduction': best_ssr_reduction,
        'slope_ratio': best_slope_ratio,
        'expected_bp': 30,
        'expected_ssr': 90.2,
        'pass': abs(best_bp - 30) <= 5 and abs(best_ssr_reduction - 90.2) < 5
    }


def validate_wvss_weights(component_path):
    """
    Validate wVSS component weights.
    
    Expected: Velocity ~97.22%, Pitch ~0.39%, Temporal ~2.39%
    """
    df = pd.read_csv(component_path)
    
    # Calculate effect sizes for each component
    control = df[df['Condition'] == 'Control']
    multi = df[df['Condition'] == 'Multi-Constraint']
    
    effects = {}
    for comp in ['Pitch Distance', 'Velocity Distance', 'Temporal Distance']:
        ctrl_val = control[control['Component'] == comp]['Mean'].values[0]
        multi_val = multi[multi['Component'] == comp]['Mean'].values[0]
        effects[comp] = abs(multi_val - ctrl_val)
    
    total = sum(effects.values())
    weights = {k: v/total*100 for k, v in effects.items()}
    
    return {
        'pitch_weight': weights.get('Pitch Distance', 0),
        'velocity_weight': weights.get('Velocity Distance', 0),
        'temporal_weight': weights.get('Temporal Distance', 0),
        'expected_velocity': 97.22,
        'pass': weights.get('Velocity Distance', 0) > 90
    }


if __name__ == "__main__":
    print("=" * 60)
    print("RQ3 COHERENCE THRESHOLDS VALIDATION")
    print("=" * 60)
    
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'csv')
    
    # Validate breakpoint
    coherence_path = os.path.join(data_dir, 'coherence_density_results.csv')
    if os.path.exists(coherence_path):
        bp_results = validate_melodic_breakpoint(coherence_path)
        status = "✅ PASS" if bp_results['pass'] else "⚠️ CHECK"
        print(f"\nMELODIC BREAKPOINT:")
        print(f"  Detected: {bp_results['breakpoint']} notes/s (expected: 30)")
        print(f"  SSR reduction: {bp_results['ssr_reduction']:.1f}% (expected: 90.2%)")
        print(f"  Status: {status}")
    
    # Validate wVSS weights
    component_path = os.path.join(data_dir, 'vss_component_analysis_results.csv')
    if os.path.exists(component_path):
        wvss_results = validate_wvss_weights(component_path)
        status = "✅ PASS" if wvss_results['pass'] else "⚠️ CHECK"
        print(f"\nwVSS WEIGHTS:")
        print(f"  Pitch: {wvss_results['pitch_weight']:.2f}%")
        print(f"  Velocity: {wvss_results['velocity_weight']:.2f}% (expected: ~97%)")
        print(f"  Temporal: {wvss_results['temporal_weight']:.2f}%")
        print(f"  Status: {status}")
