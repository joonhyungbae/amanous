#!/usr/bin/env python3
"""
RETIRED -- kept for the record only; not a source for the published paper.

An earlier draft claimed a sharp coherence-saturation threshold and a
distribution-independence experiment. Both were withdrawn during review. The
paper's density result comes from code/discriminability_analysis.py. See the
"Reproducing the paper" section of the README.
"""
"""
Aggregate Density vs Single-Voice Coherence: Linear vs Piecewise Regression.

- Loads density_sweep_results.csv (columns: Aggregate Density, Single-Voice Coherence).
- Fits (1) simple linear regression, (2) piecewise/segmented regression.
- Compares R² and reports optimal breakpoint ρ̂.
- If piecewise R² is substantially higher, supports 'Computational Phase Transition' interpretation.
- Saves plot to threshold_analysis.png.
"""

import os
import argparse
import numpy as np
import pandas as pd
from scipy import optimize
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# Expected CSV: density (notes/s), single-voice coherence (normalised 0–1 preferred)
DEFAULT_CSV = "density_sweep_results.csv"


def _find_columns(df: pd.DataFrame):
    """Resolve 'density' and 'coherence' columns from CSV (flexible names)."""
    cols = [c.strip() for c in df.columns]
    low = [c.lower() for c in cols]
    density_col = None
    for name in ("aggregate density", "aggregate_density", "density", "density_notes_per_s"):
        for i, c in enumerate(low):
            if name in c or c == name.replace("_", " "):
                density_col = df.columns[i]
                break
        if density_col is not None:
            break
    if density_col is None:
        density_col = df.columns[0]

    coherence_col = None
    for name in (
        "single-voice coherence", "single_voice_coherence", "coherence",
        "melodic_coherence", "single_voice_coherence_normalised"
    ):
        for i, c in enumerate(low):
            if name in c or c == name.replace("_", " ").replace("-", " "):
                coherence_col = df.columns[i]
                break
        if coherence_col is not None:
            break
    if coherence_col is None:
        # fallback: second column or first numeric column that is not density
        for c in df.columns:
            if c != density_col and pd.api.types.is_numeric_dtype(df[c]):
                coherence_col = c
                break
        if coherence_col is None:
            coherence_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
    return density_col, coherence_col


def _normalize_coherence(y: np.ndarray) -> np.ndarray:
    """Scale to [0, 1] if values are not in that range (e.g. raw entropy)."""
    y = np.asarray(y, dtype=float)
    if np.any(np.isnan(y)):
        y = np.nan_to_num(y, nan=np.nanmean(y))
    mn, mx = np.nanmin(y), np.nanmax(y)
    if mx - mn < 1e-10:
        return np.clip(y, 0, 1)
    if mn < -0.01 or mx > 1.01:
        return (y - mn) / (mx - mn)
    return y


def fit_segment(x: np.ndarray, y: np.ndarray):
    """OLS for y ~ x. Returns (intercept, slope), rss."""
    x, y = np.asarray(x), np.asarray(y)
    if len(x) < 2:
        return np.nan, np.nan, np.inf
    X = np.column_stack([np.ones_like(x), x])
    beta, rss, _, _ = np.linalg.lstsq(X, y, rcond=None)
    rss_val = float(rss[0]) if np.size(rss) else float(np.sum((y - X @ beta) ** 2))
    return float(beta[0]), float(beta[1]), rss_val


def rss_piecewise(bp: float, x: np.ndarray, y: np.ndarray) -> float:
    """Total RSS for piecewise linear: left x < bp, right x >= bp."""
    x, y = np.asarray(x), np.asarray(y)
    left = x < bp
    right = x >= bp
    if np.sum(left) < 2 or np.sum(right) < 2:
        return 1e30
    _, _, rss_left = fit_segment(x[left], y[left])
    _, _, rss_right = fit_segment(x[right], y[right])
    return rss_left + rss_right


def fit_piecewise_at_bp(x: np.ndarray, y: np.ndarray, bp: float):
    """Given breakpoint bp, return (a1, b1, a2, b2, rss_total)."""
    left = x < bp
    right = x >= bp
    a1, b1, rss_left = fit_segment(x[left], y[left])
    a2, b2, rss_right = fit_segment(x[right], y[right])
    return a1, b1, a2, b2, rss_left + rss_right


def estimate_breakpoint(
    x: np.ndarray, y: np.ndarray,
    bp_min: float = None, bp_max: float = None,
) -> float:
    """Find breakpoint minimising RSS in (bp_min, bp_max)."""
    x = np.asarray(x)
    if bp_min is None:
        bp_min = np.percentile(x, 15)
    if bp_max is None:
        bp_max = np.percentile(x, 85)
    bp_min = max(bp_min, x.min() + 1e-6)
    bp_max = min(bp_max, x.max() - 1e-6)
    if bp_max <= bp_min:
        bp_max = x.max() - 1e-6
        bp_min = x.min() + 1e-6
    res = optimize.minimize_scalar(
        rss_piecewise, bounds=(float(bp_min), float(bp_max)),
        method="bounded", args=(x, y),
    )
    return float(res.x)


def r2_linear(x: np.ndarray, y: np.ndarray) -> float:
    """R² for simple linear regression y ~ x."""
    _, _, rss = fit_segment(x, y)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    return float(1 - rss / ss_tot) if ss_tot > 0 else 0.0


def main():
    parser = argparse.ArgumentParser(description="Density–Coherence threshold analysis (linear vs piecewise).")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Path to density_sweep_results.csv")
    parser.add_argument("--out", default="threshold_analysis.png", help="Output plot path")
    parser.add_argument("--no-normalize", action="store_true", help="Do not normalize coherence to [0,1]")
    args = parser.parse_args()

    csv_path = args.csv
    if not os.path.isabs(csv_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        for base in (script_dir, os.getcwd()):
            cand = os.path.join(base, csv_path)
            if os.path.isfile(cand):
                csv_path = cand
                break
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(
            f"CSV not found: {args.csv}. "
            "Provide density_sweep_results.csv with columns 'Aggregate Density' (or 'density') and 'Single-Voice Coherence' (or 'coherence')."
        )

    df = pd.read_csv(csv_path)
    density_col, coherence_col = _find_columns(df)
    df = df[[density_col, coherence_col]].dropna()
    x = df[density_col].values.astype(float)
    y = df[coherence_col].values.astype(float)
    if not args.no_normalize:
        y = _normalize_coherence(y)
    n = len(x)
    if n < 4:
        raise ValueError("Need at least 4 (density, coherence) pairs.")

    # Simple linear regression
    a_lin, b_lin, rss_lin = fit_segment(x, y)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2_linear_val = float(1 - rss_lin / ss_tot) if ss_tot > 0 else 0.0

    # Piecewise regression and optimal breakpoint ρ̂
    rho_hat = estimate_breakpoint(x, y)
    a1, b1, a2, b2, rss_pw = fit_piecewise_at_bp(x, y, rho_hat)
    r2_piecewise = float(1 - rss_pw / ss_tot) if ss_tot > 0 else 0.0

    # Predictions for plotting
    x_plot = np.linspace(x.min(), x.max(), 300)
    y_linear = a_lin + b_lin * x_plot
    left_plot = x_plot < rho_hat
    right_plot = x_plot >= rho_hat
    y_piecewise = np.where(left_plot, a1 + b1 * x_plot, a2 + b2 * x_plot)

    # Figure
    fig, ax = plt.subplots(1, 1, figsize=(7, 5))
    ax.scatter(x, y, color="black", s=36, alpha=0.8, label="Data", zorder=3)
    ax.plot(x_plot, y_linear, color="gray", ls="--", lw=1.5, label=f"Linear ($R^2$ = {r2_linear_val:.3f})")
    ax.plot(x_plot, y_piecewise, color="steelblue", lw=2, label=f"Piecewise ($R^2$ = {r2_piecewise:.3f})")
    ax.axvline(rho_hat, color="coral", ls=":", lw=1.5, label=f"Breakpoint $\\hat{{\\rho}}$ = {rho_hat:.1f} notes/s")
    ax.set_xlabel("Aggregate Density (notes/s)")
    ax.set_ylabel("Single-Voice Coherence (normalised)")
    ax.set_title("Density–Coherence: Linear vs Piecewise Regression")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(x.min() - 2, x.max() + 2)
    fig.tight_layout()
    out_path = args.out
    if not os.path.isabs(out_path):
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), out_path)
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Plot saved: {out_path}")

    # Console summary
    print("\n--- Threshold analysis ---")
    print(f"  Linear R²:     {r2_linear_val:.4f}")
    print(f"  Piecewise R²:  {r2_piecewise:.4f}")
    print(f"  Breakpoint ρ̂:  {rho_hat:.2f} notes/s")
    print(f"  Pre-breakpoint slope:  {b1:.4f}")
    print(f"  Post-breakpoint slope: {b2:.4f}")
    if abs(b2) > 1e-10:
        print(f"  Slope ratio (pre/post): {b1/b2:.2f}×")
    delta_r2 = r2_piecewise - r2_linear_val
    if delta_r2 > 0.05:
        print("\n  → Piecewise model explains substantially more variance (ΔR² = {:.3f}).".format(delta_r2))
        print("    This supports a 'Computational Phase Transition' at ρ̂.")
    else:
        print("\n  → Improvement of piecewise over linear is modest (ΔR² = {:.3f}).".format(delta_r2))


if __name__ == "__main__":
    main()
