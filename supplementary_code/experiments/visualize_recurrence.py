#!/usr/bin/env python3
"""
Recurrence Plot visualization and DET comparison: L-System vs same-composition Random sequence.

- Build Random sequence by shuffling with same A:B ratio as L-System.
- Build Recurrence Plot (symbol recurrence matrix) for both.
- Visual contrast: L-System diagonal structure vs Random fragmented points.
- Compute Determinism (DET); output table showing L-System significantly higher than random.

Run: python visualize_recurrence.py [--depth 8] [--n_shuffle 200] [--seed 42]
"""

import sys
import argparse
import numpy as np
from collections import Counter

# Visualization (optional)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def lsystem_expand(axiom: str, rules: dict, depth: int) -> str:
    """L-system expansion: axiom, rules (e.g. A->AB, B->A), depth."""
    current = axiom
    for _ in range(depth):
        current = "".join(rules.get(s, s) for s in current)
    return current


def shuffled_preserve_composition(sequence: str, rng: np.random.Generator) -> str:
    """Preserve same composition ratio, shuffle order only."""
    chars = list(sequence)
    rng.shuffle(chars)
    return "".join(chars)


def recurrence_matrix_symbolic(sequence: str) -> np.ndarray:
    """
    Recurrence matrix for symbol sequence.
    R[i,j] = 1 if sequence[i] == sequence[j], else 0.
    """
    n = len(sequence)
    R = np.zeros((n, n), dtype=np.uint8)
    for i in range(n):
        for j in range(n):
            if sequence[i] == sequence[j]:
                R[i, j] = 1
    return R


def diagonal_line_lengths(R: np.ndarray, exclude_main: bool = True) -> list:
    """
    Collect lengths of runs of 1 along diagonals (parallel to main diagonal).
    exclude_main: if True, skip main diagonal (k=0) (self-match excluded).
    """
    n = R.shape[0]
    lengths = []
    # k = j - i (diagonal index). k=0 is main diagonal.
    for k in range(-n + 1, n):
        if k == 0 and exclude_main:
            continue
        # Valid (i, i+k) range
        if k >= 0:
            is_ = np.arange(0, n - k)
            js_ = is_ + k
        else:
            js_ = np.arange(0, n + k)
            is_ = js_ - k
        line = R[is_, js_]
        # Run lengths of consecutive 1s
        runs = []
        in_run = False
        run_len = 0
        for v in line:
            if v == 1:
                if not in_run:
                    in_run = True
                    run_len = 1
                else:
                    run_len += 1
            else:
                if in_run:
                    runs.append(run_len)
                    in_run = False
        if in_run:
            runs.append(run_len)
        lengths.extend(runs)
    return lengths


def determinism_rqa(lengths: list, l_min: int = 2) -> float:
    """
    RQA Determinism: DET = sum(l*P(l)) for l>=l_min / sum(l*P(l)) for all l.
    P(l) = count of lines of length l.
    """
    if not lengths:
        return 0.0
    hist = Counter(lengths)
    total_weight = sum(l * c for l, c in hist.items())
    if total_weight <= 0:
        return 0.0
    det_weight = sum(l * hist[l] for l in hist if l >= l_min)
    return det_weight / total_weight


def compute_det(sequence: str, l_min: int = 2, exclude_main: bool = True) -> float:
    """Compute Recurrence matrix for sequence and return DET."""
    R = recurrence_matrix_symbolic(sequence)
    lengths = diagonal_line_lengths(R, exclude_main=exclude_main)
    return determinism_rqa(lengths, l_min=l_min)


def run_comparison(depth: int, n_shuffle: int, seed: int, l_min: int = 2) -> dict:
    """Compute DET for L-system sequence and n_shuffle shuffles; return sequences/matrices."""
    axiom, rules = "A", {"A": "AB", "B": "A"}
    seq_lsystem = lsystem_expand(axiom, rules, depth)
    rng = np.random.default_rng(seed)

    det_lsystem = compute_det(seq_lsystem, l_min=l_min)
    det_shuffled = []
    for _ in range(n_shuffle):
        seq_shuffled = shuffled_preserve_composition(seq_lsystem, rng)
        det_shuffled.append(compute_det(seq_shuffled, l_min=l_min))

    det_shuffled = np.array(det_shuffled)
    # Permutation p-value: P(DET_random >= DET_lsystem) under null
    p_value = np.mean(det_shuffled >= det_lsystem)
    # one-sided: test L-system higher -> p = P(null >= observed)
    p_value_onesided = np.mean(det_shuffled >= det_lsystem)

    return {
        "depth": depth,
        "length": len(seq_lsystem),
        "seq_lsystem": seq_lsystem,
        "seq_random_example": shuffled_preserve_composition(seq_lsystem, np.random.default_rng(seed + 1)),
        "DET_Lsystem": det_lsystem,
        "DET_Random_mean": float(np.mean(det_shuffled)),
        "DET_Random_std": float(np.std(det_shuffled, ddof=1)),
        "DET_Random_min": float(np.min(det_shuffled)),
        "DET_Random_max": float(np.max(det_shuffled)),
        "n_shuffle": n_shuffle,
        "p_value": p_value_onesided,
        "significant": p_value_onesided < 0.05,
    }


def plot_recurrence_plots(
    seq_lsystem: str,
    seq_random: str,
    out_path: str = "recurrence_plot_comparison.png",
    figsize: tuple = (10, 5),
):
    """Save L-System and Random Recurrence Plots side by side."""
    if not HAS_MATPLOTLIB:
        print("matplotlib not found. Skipping Recurrence Plot image.")
        return
    R_l = recurrence_matrix_symbolic(seq_lsystem)
    R_r = recurrence_matrix_symbolic(seq_random)
    plt.rcParams.update({"font.size": 15, "axes.titlesize": 15})
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
    ax1.imshow(R_l, cmap="binary", origin="lower", aspect="equal")
    ax1.set_title("L-system")
    ax1.set_xlabel("Index $j$")
    ax1.set_ylabel("Index $i$")
    ax2.imshow(R_r, cmap="binary", origin="lower", aspect="equal")
    ax2.set_title("Random shuffle (same A:B)")
    ax2.set_xlabel("Index $j$")
    ax2.set_ylabel("Index $i$")
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


def print_det_table(results: list):
    """Print DET comparison and statistical significance table."""
    if not results:
        return
    print("\n" + "=" * 90)
    print("Recurrence Quantification: Determinism (DET) — L-System vs Random (same composition)")
    print("=" * 90)
    print(
        f"{'Depth':<8} {'|S|':<8} {'DET (L-System)':<18} {'DET (Random) mean±std':<28} {'p-value':<12} {'Significant':<12}"
    )
    print("-" * 90)
    for r in results:
        sig = "Yes" if r["significant"] else "No"
        rand_str = f"{r['DET_Random_mean']:.4f} ± {r['DET_Random_std']:.4f}"
        print(
            f"{r['depth']:<8} {r['length']:<8} {r['DET_Lsystem']:<18.4f} {rand_str:<28} {r['p_value']:<12.4f} {sig:<12}"
        )
    print("=" * 90)
    print("\nDET = proportion of recurrence points forming diagonal lines (length ≥ 2).")
    print("p-value = proportion of random shuffles with DET ≥ L-System DET (one-sided).")
    print("Significant: p < 0.05 → L-System has higher structural determinism than random.\n")


def main():
    parser = argparse.ArgumentParser(
        description="L-System vs Random Recurrence Plot and DET comparison"
    )
    parser.add_argument("--depth", type=int, default=8, help="L-system depth (default: 8)")
    parser.add_argument(
        "--n_shuffle",
        type=int,
        default=200,
        help="Number of random shuffles for null distribution (default: 200)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--l_min", type=int, default=2, help="Minimum diagonal line length for DET")
    parser.add_argument(
        "--depths",
        type=str,
        default=None,
        help="Comma-separated depths for table (e.g. 4,6,8). Overrides --depth for table.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="recurrence_plot_comparison.png",
        help="Output path for recurrence plot figure",
    )
    parser.add_argument("--no-plot", action="store_true", help="Skip saving recurrence plot image")
    args = parser.parse_args()

    depths = [int(x.strip()) for x in args.depths.split(",")] if args.depths else [args.depth]
    results = [
        run_comparison(d, n_shuffle=args.n_shuffle, seed=args.seed, l_min=args.l_min)
        for d in depths
    ]

    print_det_table(results)

    if HAS_MATPLOTLIB and not args.no_plot:
        # Use first depth result for plot (or longest sequence)
        r = max(results, key=lambda x: x["length"])
        plot_recurrence_plots(
            r["seq_lsystem"],
            r["seq_random_example"],
            out_path=args.out,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
