#!/usr/bin/env python3
"""
Generate per-fold equity plots and a short backtest report.

Saves PNGs to `backtest_results/figures/` and a markdown report to
`backtest_results/report.md`.
"""
import os
import glob
import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


OUT_DIR = Path("backtest_results/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def max_drawdown(equity):
    roll_max = equity.cummax()
    drawdown = (roll_max - equity) / roll_max
    return float(drawdown.max())


report_lines = []
report_lines.append("# Backtest Report\n")

# Summaries per model/fold
report_lines.append("## Per-model / per-fold summaries\n")
summary = {}
model_dirs = sorted(glob.glob("backtest_results/walkforward_per_model/*"))
for model_dir in model_dirs:
    model_tag = os.path.basename(model_dir)
    equity_files = sorted(glob.glob(os.path.join(model_dir, "fold*_equity.csv")))
    if not equity_files:
        continue
    summary[model_tag] = []
    # combined plot
    plt.figure(figsize=(10, 5))
    for ef in equity_files:
        try:
            df = pd.read_csv(ef)
        except Exception:
            continue
        # try to find equity column
        equity_col = None
        for c in ("equity", "capital", "account_equity"):
            if c in df.columns:
                equity_col = c
                break
        if equity_col is None:
            # fallback to last numeric column
            numerics = df.select_dtypes("number")
            if numerics.shape[1] == 0:
                continue
            equity_col = numerics.columns[-1]

        s = df[equity_col].astype(float)
        fold_name = Path(ef).stem
        # per-fold plot
        plt.plot(s.values, label=fold_name)

        total_pnl = float(s.iloc[-1] - s.iloc[0])
        mdd = max_drawdown(s)
        summary[model_tag].append({"fold": fold_name, "total_pnl": total_pnl, "max_drawdown": mdd, "file": ef})

    plt.title(f"Equity curves — {model_tag}")
    plt.legend(loc="best", fontsize="small")
    plt.tight_layout()
    outpng = OUT_DIR / f"{model_tag}_combined_equity.png"
    plt.savefig(outpng)
    plt.close()

    # save individual plots too
    for item in summary[model_tag]:
        try:
            df = pd.read_csv(item["file"])
        except Exception:
            continue
        equity_col = None
        for c in ("equity", "capital", "account_equity"):
            if c in df.columns:
                equity_col = c
                break
        if equity_col is None:
            numerics = df.select_dtypes("number")
            equity_col = numerics.columns[-1]
        s = df[equity_col].astype(float)
        plt.figure(figsize=(8, 4))
        plt.plot(s.values)
        plt.title(f"{model_tag} — {item['fold']}")
        plt.tight_layout()
        outpng = OUT_DIR / f"{model_tag}_{item['fold']}_equity.png"
        plt.savefig(outpng)
        plt.close()

    # write model section
    report_lines.append(f"### {model_tag}\n")
    for item in summary[model_tag]:
        report_lines.append(f"- **{item['fold']}**: total_pnl = {item['total_pnl']:.6f}, max_drawdown = {item['max_drawdown']:.6f}")
    report_lines.append("\n")

# Include walk-forward CSV summary if present
wf_csv = Path("backtest_results/ml_vs_rule_walkforward.csv")
if wf_csv.exists():
    try:
        dfw = pd.read_csv(wf_csv)
        report_lines.append("## Walk-forward summary (ml_vs_rule_walkforward.csv)\n")
        # show basic aggregated stats
        report_lines.append(f"- Rows: {len(dfw)}\n")
        # include top/bottom folds by total_pnl if available
        if "total_pnl" in dfw.columns and "mode" in dfw.columns:
            for mode in dfw["mode"].unique():
                sub = dfw[dfw["mode"] == mode]
                mean_pnl = sub["total_pnl"].mean()
                report_lines.append(f"- {mode}: mean total_pnl = {mean_pnl:.6f} ({len(sub)} folds)")
            report_lines.append("\n")
    except Exception:
        pass

# Write report
report_path = Path("backtest_results/report.md")
report_path.write_text("\n".join(report_lines))
print("Wrote plots to", OUT_DIR)
print("Wrote report to", report_path)
