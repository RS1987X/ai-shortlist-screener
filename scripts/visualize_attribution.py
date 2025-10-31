#!/usr/bin/env python3
"""
Generate visualizations for LAR attribution.

- Input: data/lar_scores_attribution.csv (from `asr lar ...`)
- Output: PNG charts under data/figures/

Charts:
1) Stacked horizontal bar (top-N peers by LAR): E/X/A/S contributions
   - Vertical marker at actual LAR (shows effect of E<60 cap when present)
2) Optional single-peer breakdown (if --peer provided)

Usage:
  python scripts/visualize_attribution.py \
    --attrib-csv data/lar_scores_attribution.csv \
    --out-dir data/figures \
    --top 20

Optional:
  python scripts/visualize_attribution.py --peer "Elgiganten"  # exact Brand match
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def pick_col(df: pd.DataFrame, *names: str) -> str:
    for n in names:
        if n in df.columns:
            return n
    raise KeyError(f"None of the expected columns found: {names}")


def load_attribution(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Map to internal names, tolerating both machine and human-friendly headers
    colmap = {}
    colmap['domain'] = pick_col(df, 'key', 'Domain', 'domain')
    colmap['brand'] = pick_col(df, 'brand', 'Brand')
    colmap['lar'] = pick_col(df, 'LAR', 'lar')

    # Contributions
    colmap['E_contrib'] = pick_col(df, 'E_contrib', 'E contribution to LAR')
    colmap['X_contrib'] = pick_col(df, 'X_contrib', 'X contribution to LAR')
    colmap['A_contrib'] = pick_col(df, 'A_contrib', 'A contribution to LAR')
    colmap['S_contrib'] = pick_col(df, 'S_contrib', 'S contribution to LAR')

    # Raw dimensions (optional, for labeling)
    colmap['E'] = pick_col(df, 'E', 'E (Eligibility)') if any(c in df.columns for c in ['E', 'E (Eligibility)']) else None
    colmap['X'] = pick_col(df, 'X', 'X (eXtensibility)') if any(c in df.columns for c in ['X', 'X (eXtensibility)']) else None
    colmap['A'] = pick_col(df, 'A', 'A (Share of Answer)') if any(c in df.columns for c in ['A', 'A (Share of Answer)']) else None
    colmap['S'] = pick_col(df, 'S', 'S (Sentiment)') if any(c in df.columns for c in ['S', 'S (Sentiment)']) else None

    out = pd.DataFrame()
    for k, v in colmap.items():
        if v is not None:
            out[k] = df[v]
    # Compute cap penalty (formula sum - actual LAR)
    out['raw_sum'] = out['E_contrib'] + out['X_contrib'] + out['A_contrib'] + out['S_contrib']
    out['cap_penalty'] = (out['raw_sum'] - out['lar']).clip(lower=0)
    return out


def plot_topn_stacked(df: pd.DataFrame, out_path: Path, top: int = 20):
    d = df.copy()
    d['order'] = d['lar'].rank(method='first', ascending=False)
    d = d.sort_values('lar', ascending=True).tail(top)  # keep top N, keep ascending for horizontal bars

    brands = d['brand'].tolist()
    y = range(len(d))

    plt.figure(figsize=(12, max(6, 0.5*len(d))))
    left = [0]*len(d)
    colors = {
        'E_contrib': '#377eb8',  # blue
        'X_contrib': '#4daf4a',  # green
        'A_contrib': '#984ea3',  # purple
        'S_contrib': '#ff7f00',  # orange
    }
    labels = {
        'E_contrib': 'E contribution',
        'X_contrib': 'X contribution',
        'A_contrib': 'A contribution',
        'S_contrib': 'S contribution',
    }
    for key in ['E_contrib', 'X_contrib', 'A_contrib', 'S_contrib']:
        vals = d[key].tolist()
        plt.barh(y, vals, left=left, color=colors[key], edgecolor='white', label=labels[key])
        left = [l+v for l, v in zip(left, vals)]

    # Draw vertical marker at actual LAR per row (shows cap effect when LAR < raw_sum)
    lar_vals = d['lar'].tolist()
    for yi, lar_val in zip(y, lar_vals):
        plt.vlines(lar_val, yi-0.4, yi+0.4, colors='k', linewidth=1)

    # Annotate cap penalty if any
    penalties = d['cap_penalty'].tolist()
    for yi, pen, total in zip(y, penalties, d['raw_sum'].tolist()):
        if pen > 0.1:
            plt.text(total + 0.5, yi, f"cap -{pen:.1f}", va='center', ha='left', fontsize=8, color='crimson')

    plt.yticks(y, brands)
    plt.xlabel('Points')
    plt.title(f'LAR contributions (top {top}) — vertical tick = actual LAR (after cap)')
    plt.legend(loc='lower right', ncol=2)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def plot_single_peer(df: pd.DataFrame, brand: str, out_path: Path):
    d = df[df['brand'] == brand]
    if d.empty:
        raise SystemExit(f"Peer '{brand}' not found in attribution data.")
    row = d.iloc[0]
    parts = {
        'E': row['E_contrib'],
        'X': row['X_contrib'],
        'A': row['A_contrib'],
        'S': row['S_contrib'],
    }
    plt.figure(figsize=(8, 4))
    keys = list(parts.keys())
    vals = [parts[k] for k in keys]
    colors = ['#377eb8', '#4daf4a', '#984ea3', '#ff7f00']
    plt.bar(keys, vals, color=colors)
    # Draw LAR line
    plt.axhline(row['lar'], color='k', linestyle='--', linewidth=1)
    if row['cap_penalty'] > 0.1:
        plt.text(3.6, row['lar']+0.5, f"LAR (capped) {row['lar']:.1f}", ha='right', va='bottom', fontsize=9)
    else:
        plt.text(3.6, row['lar']+0.5, f"LAR {row['lar']:.1f}", ha='right', va='bottom', fontsize=9)
    plt.ylabel('Points')
    plt.title(f"{brand} — contributions vs LAR")
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def plot_topn_component_contributions(df: pd.DataFrame, raw_df: pd.DataFrame, out_path: Path, top: int = 20):
    """Detailed top-N chart: shows underlying scores that drove each dimension."""
    # Build DataFrame with needed fields (tolerate human-friendly headers)
    def getcol(df_in, a, b=None):
        if a in df_in.columns:
            return df_in[a]
        if b and b in df_in.columns:
            return df_in[b]
        return pd.Series([None] * len(df_in))

    merged = pd.DataFrame({
        'brand': df['brand'],
        'lar': df['lar'],
        'A_contrib': df['A_contrib'],
        'S_contrib': df['S_contrib'],
        'E_contrib': df['E_contrib'],
        'X_contrib': df['X_contrib'],
        # Underlying scores
        'E': getcol(raw_df, 'E', 'E (Eligibility)'),
        'X': getcol(raw_df, 'X', 'X (eXtensibility)'),
        'A': getcol(raw_df, 'A', 'A (Share of Answer)'),
        'S': getcol(raw_df, 'S', 'S (Sentiment)'),
        'E_product_avg': getcol(raw_df, 'E_product_avg', 'E: product score avg'),
        'E_family_avg': getcol(raw_df, 'E_family_avg', 'E: family score avg'),
        'X_policy_points_avg': getcol(raw_df, 'X_policy_points_avg', 'X: policy points avg'),
        'X_specs_points_avg': getcol(raw_df, 'X_specs_points_avg', 'X: specs points avg'),
        'S_rating': getcol(raw_df, 'S_raw_rating_avg', 'S: average star rating'),
        'S_count': getcol(raw_df, 'S_rating_count_avg', 'S: average rating count'),
        'S_conf': getcol(raw_df, 'S_confidence_avg', 'S: average confidence'),
    })

    # Component contributions (LAR points)
    merged['E_product_contrib'] = 0.40 * 0.8 * merged['E_product_avg'].fillna(0).astype(float)
    merged['E_family_contrib'] = 0.40 * 0.2 * merged['E_family_avg'].fillna(0).astype(float)
    merged['X_policy_contrib'] = 0.25 * merged['X_policy_points_avg'].fillna(0).astype(float)
    merged['X_specs_contrib'] = 0.25 * merged['X_specs_points_avg'].fillna(0).astype(float)

    d = merged.sort_values('lar', ascending=True).tail(top)
    y = range(len(d))
    brands = d['brand'].tolist()

    plt.figure(figsize=(16, max(8, 0.7*len(d))))
    left = [0]*len(d)

    colors = {
        'E_product_contrib': '#6baed6',  # light blue
        'E_family_contrib': '#2171b5',   # dark blue
        'X_policy_contrib': '#74c476',   # light green
        'X_specs_contrib': '#238b45',    # dark green
        'A_contrib': '#9e9ac8',          # light purple
        'S_contrib': '#fd8d3c',          # orange
    }
    order = ['E_product_contrib','E_family_contrib','X_policy_contrib','X_specs_contrib','A_contrib','S_contrib']
    labels = {
        'E_product_contrib': 'E: product',
        'E_family_contrib': 'E: family',
        'X_policy_contrib': 'X: policy',
        'X_specs_contrib': 'X: specs',
        'A_contrib': 'A',
        'S_contrib': 'S',
    }
    for key in order:
        vals = d[key].tolist()
        plt.barh(y, vals, left=left, color=colors[key], edgecolor='white', label=labels[key])
        left = [l+v for l, v in zip(left, vals)]

    # LAR ticks
    lar_vals = d['lar'].tolist()
    for yi, lar_val in zip(y, lar_vals):
        plt.vlines(lar_val, yi-0.4, yi+0.4, colors='k', linewidth=1)

    # Annotate with meaningful underlying scores
    for idx, yi in enumerate(y):
        row = d.iloc[idx]
        # Build annotation with actual values
        parts = []
        # E scores (raw 0-100)
        e_prod = float(row['E_product_avg']) if pd.notna(row['E_product_avg']) else 0.0
        e_fam = float(row['E_family_avg']) if pd.notna(row['E_family_avg']) else 0.0
        parts.append(f"E={row['E']:.0f} (prod:{e_prod:.0f} fam:{e_fam:.0f})")
        
        # X scores (raw points 0-100)
        x_pol = float(row['X_policy_points_avg']) if pd.notna(row['X_policy_points_avg']) else 0.0
        x_sp = float(row['X_specs_points_avg']) if pd.notna(row['X_specs_points_avg']) else 0.0
        parts.append(f"X={row['X']:.0f} (pol:{x_pol:.0f} sp:{x_sp:.0f})")
        
        # A score
        parts.append(f"A={row['A']:.0f}")
        
        # S with context
        s_rating = float(row['S_rating']) if pd.notna(row['S_rating']) else 0.0
        s_count = float(row['S_count']) if pd.notna(row['S_count']) else 0.0
        s_conf = float(row['S_conf']) if pd.notna(row['S_conf']) else 0.0
        if s_rating > 0:
            parts.append(f"S={row['S']:.0f} (★{s_rating:.1f} n={s_count:.0f} conf={s_conf:.0%})")
        else:
            parts.append(f"S={row['S']:.0f} (no ratings)")
        
        txt = '\n'.join(parts)
        plt.text(max(left)+2, yi, txt, va='center', ha='left', fontsize=7, family='monospace', color='#333')

    plt.yticks(y, brands)
    plt.xlabel('LAR points (stacked components)')
    plt.title(f'Detailed LAR breakdown (top {top}) — tick = actual LAR, right = underlying scores')
    plt.legend(loc='lower right', ncol=3, fontsize=9)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def plot_single_peer_detailed(df: pd.DataFrame, raw_df: pd.DataFrame, brand: str, out_path: Path):
    d = df[df['brand'] == brand]
    if d.empty:
        raise SystemExit(f"Peer '{brand}' not found in attribution data.")
    row = d.iloc[0]

    def getval(col_a, col_b=None, default=0.0):
        if col_a in raw_df.columns:
            return float(raw_df.loc[row.name, col_a])
        if col_b and col_b in raw_df.columns:
            return float(raw_df.loc[row.name, col_b])
        return default

    # Raw underlying scores
    e_raw = getval('E', 'E (Eligibility)')
    x_raw = getval('X', 'X (eXtensibility)')
    a_raw = getval('A', 'A (Share of Answer)')
    s_raw = getval('S', 'S (Sentiment)')
    
    e_prod = getval('E_product_avg', 'E: product score avg')
    e_fam = getval('E_family_avg', 'E: family score avg')
    x_policy = getval('X_policy_points_avg', 'X: policy points avg')
    x_specs = getval('X_specs_points_avg', 'X: specs points avg')
    raw_rating = getval('S_raw_rating_avg', 'S: average star rating')
    rating_count = getval('S_rating_count_avg', 'S: average rating count')
    conf = getval('S_confidence_avg', 'S: average confidence')
    src_w = getval('S_source_weight_avg', 'S: average source weight')
    fallback = getval('S_fallback_share', 'S: fallback share')

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    ax1, ax2, ax3, ax4 = axes.ravel()

    # E breakdown: show raw scores and contributions
    e_prod_c = 0.40 * 0.8 * e_prod
    e_fam_c = 0.40 * 0.2 * e_fam
    ax1.barh(['Product\n(80% weight)', 'Family\n(20% weight)'], [e_prod_c, e_fam_c], 
             color=['#6baed6', '#2171b5'])
    ax1.set_xlabel('LAR points')
    ax1.set_title(f'E (Eligibility) = {e_raw:.1f} → {row["E_contrib"]:.2f} LAR pts')
    for i, (label, raw, contrib) in enumerate([('Product', e_prod, e_prod_c), ('Family', e_fam, e_fam_c)]):
        ax1.text(contrib + 0.5, i, f'raw: {raw:.1f}/100', va='center', fontsize=9)

    # X breakdown: show raw points and contributions
    x_pol_c = 0.25 * x_policy
    x_sp_c = 0.25 * x_specs
    ax2.barh(['Policy\n(max 50pts)', 'Specs\n(max 50pts)'], [x_pol_c, x_sp_c], 
             color=['#74c476', '#238b45'])
    ax2.set_xlabel('LAR points')
    ax2.set_title(f'X (eXtensibility) = {x_raw:.1f} → {row["X_contrib"]:.2f} LAR pts')
    for i, (label, raw, contrib) in enumerate([('Policy', x_policy, x_pol_c), ('Specs', x_specs, x_sp_c)]):
        ax2.text(contrib + 0.5, i, f'raw: {raw:.1f}/50', va='center', fontsize=9)

    # S breakdown: show rating context
    ax3.bar(['S\ncontribution'], [row['S_contrib']], color='#fd8d3c', width=0.5)
    ax3.set_ylabel('LAR points')
    ax3.set_title(f'S (Sentiment) = {s_raw:.1f} → {row["S_contrib"]:.2f} LAR pts')
    if raw_rating > 0:
        context = (f"Average rating: {raw_rating:.2f}/5 ★\n"
                  f"Review count: {rating_count:.0f}\n"
                  f"Confidence: {conf:.0%}\n"
                  f"Source weight: {src_w:.0%}\n"
                  f"Fallback used: {fallback:.0%}")
        ax3.text(0, row['S_contrib']*1.1, context, ha='center', va='bottom', fontsize=9, 
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    else:
        ax3.text(0, 0.5, 'No ratings found', ha='center', va='center', fontsize=10, color='gray')

    # A: simple bar with raw value
    ax4.bar(['A\ncontribution'], [row['A_contrib']], color='#9e9ac8', width=0.5)
    ax4.set_ylabel('LAR points')
    ax4.set_title(f'A (Share of Answer) = {a_raw:.1f} → {row["A_contrib"]:.2f} LAR pts')
    ax4.text(0, row['A_contrib']*0.5, f'Share of Answer\nraw score: {a_raw:.1f}/100', 
            ha='center', va='center', fontsize=9)

    # Overall title
    total = row['E_contrib'] + row['X_contrib'] + row['A_contrib'] + row['S_contrib']
    cap_penalty = (total - row['lar']) if total > row['lar'] else 0.0
    cap_info = f" (capped by {cap_penalty:.2f})" if cap_penalty > 0.1 else ""
    fig.suptitle(f"{brand} — LAR = {row['lar']:.2f}{cap_info}", fontsize=14, fontweight='bold')

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--attrib-csv', default='data/lar_scores_attribution.csv', help='Path to attribution CSV')
    p.add_argument('--out-dir', default='data/figures', help='Where to write figures')
    p.add_argument('--top', type=int, default=20, help='Top N peers by LAR to show')
    p.add_argument('--peer', type=str, default=None, help='Optional: exact Brand name to make a single-peer chart')
    args = p.parse_args()

    attrib_path = Path(args.attrib_csv)
    out_dir = Path(args.out_dir)

    df = load_attribution(attrib_path)
    raw_df = pd.read_csv(attrib_path)

    # Top-N stacked chart
    plot_topn_stacked(df, out_dir / f"lar_contributions_top{args.top}.png", top=args.top)
    # Detailed components chart
    plot_topn_component_contributions(df, raw_df, out_dir / f"lar_contributions_components_top{args.top}.png", top=args.top)

    # Optional single peer chart
    if args.peer:
        plot_single_peer(df, args.peer, out_dir / f"lar_contributions_{args.peer.replace(' ', '_')}.png")
        plot_single_peer_detailed(df, raw_df, args.peer, out_dir / f"lar_contributions_detailed_{args.peer.replace(' ', '_')}.png")

    print(f"Wrote figures to {out_dir}")


if __name__ == '__main__':
    main()
