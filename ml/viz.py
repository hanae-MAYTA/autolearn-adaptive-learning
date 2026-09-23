"""Shared matplotlib style for the notebooks and report figures."""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

from config import ROOT_DIR

FIGURES_DIR = ROOT_DIR / "reports" / "figures"

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_MUTED = "#52514e"
GRID = "#e4e3df"
NEUTRAL = "#a3a29c"

# Categorical slots 1-3 (validated colour-blind-safe as a set). Fixed order, never cycled.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
LEVEL_COLORS = {"beginner": ORANGE, "intermediate": BLUE, "advanced": AQUA}
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def set_style() -> None:
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.labelcolor": TEXT_MUTED,
        "axes.edgecolor": GRID,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_MUTED,
        "ytick.color": TEXT_MUTED,
        "text.color": TEXT,
        "legend.frameon": False,
        "lines.linewidth": 2,
        "axes.prop_cycle": mpl.cycler(color=[BLUE, ORANGE, AQUA]),
    })


def save(fig: plt.Figure, name: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / f"{name}.png")
