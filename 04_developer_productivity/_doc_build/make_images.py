"""Generate diagram PNGs for the lab explainer doc."""
import os
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = os.path.dirname(os.path.abspath(__file__))


def box(ax, x, y, w, h, label, color="#E8F0FE", edge="#1A73E8", fontsize=10, bold=False):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                       linewidth=1.5, edgecolor=edge, facecolor=color)
    ax.add_patch(p)
    weight = "bold" if bold else "normal"
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            fontsize=fontsize, fontweight=weight, wrap=True)


def arrow(ax, x1, y1, x2, y2, label=None, color="#555"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                        mutation_scale=14, color=color, linewidth=1.3)
    ax.add_patch(a)
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.08, label,
                ha="center", va="bottom", fontsize=9, color=color)


# ---- Diagram 1: Agent architecture ----
fig, ax = plt.subplots(figsize=(10, 6))
ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis("off")
ax.set_title("Lab 04 — Agent Architecture", fontsize=14, fontweight="bold")

box(ax, 3.5, 4.8, 3, 0.8, "User (main.py menu)", color="#FFF4D6", edge="#B8860B", bold=True)
box(ax, 3.5, 3.4, 3, 0.9, "Main Agent\n(claude-sonnet-4-6)", color="#E8F0FE", edge="#1A73E8", bold=True)

box(ax, 0.2, 1.6, 2.6, 1.1, "Built-in Tools\nRead · Write · Edit\nGrep · Glob", color="#E6F4EA", edge="#188038")
box(ax, 3.1, 1.6, 2.6, 1.1, "MCP Server: docs\nlookup_docs()\n(tools.py + data.py)", color="#FCE8E6", edge="#D93025")
box(ax, 6.0, 1.6, 2.6, 1.1, "Explore Subagent\n(agents.py)\nisolated context", color="#F3E8FD", edge="#8430CE")

box(ax, 0.2, 0.1, 8.4, 0.9,
    "Hooks: PreToolUse / PostToolUse  —  live tool-call logging (main.py)",
    color="#F1F3F4", edge="#5F6368")

arrow(ax, 5, 4.8, 5, 4.3)
arrow(ax, 4.4, 3.4, 1.5, 2.7)
arrow(ax, 5, 3.4, 4.4, 2.7)
arrow(ax, 5.6, 3.4, 7.3, 2.7)
arrow(ax, 5, 1.6, 5, 1.0, color="#888")

plt.tight_layout()
plt.savefig(os.path.join(OUT, "arch.png"), dpi=160, bbox_inches="tight")
plt.close()

# ---- Diagram 2: Query flow ----
fig, ax = plt.subplots(figsize=(10, 4.5))
ax.set_xlim(0, 10); ax.set_ylim(0, 4.5); ax.axis("off")
ax.set_title("Query Lifecycle in run_query()", fontsize=14, fontweight="bold")

steps = [
    ("1. Load prompts\n& scratch.md", "#E8F0FE", "#1A73E8"),
    ("2. Build system\nprompt + tools", "#E6F4EA", "#188038"),
    ("3. query() via\nClaudeAgentOptions", "#FFF4D6", "#B8860B"),
    ("4. Agent calls\nGrep/Read/MCP/\nsubagent", "#FCE8E6", "#D93025"),
    ("5. Hooks log\neach tool call", "#F3E8FD", "#8430CE"),
    ("6. Render reply\n(rich Markdown)", "#E0F7FA", "#00838F"),
]
x = 0.2
for label, c, e in steps:
    box(ax, x, 1.6, 1.45, 1.4, label, color=c, edge=e, fontsize=9)
    x += 1.65

for i in range(5):
    arrow(ax, 0.2 + 1.45 + i * 1.65, 2.3, 0.2 + 1.65 + i * 1.65, 2.3)

box(ax, 1.0, 0.1, 8.0, 0.8,
    "Scratchpad (scratch.md) persists findings across runs — loaded at start, written after answer.",
    color="#F1F3F4", edge="#5F6368", fontsize=10)

plt.tight_layout()
plt.savefig(os.path.join(OUT, "flow.png"), dpi=160, bbox_inches="tight")
plt.close()

print("OK")
