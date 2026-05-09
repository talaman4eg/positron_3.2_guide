#!/usr/bin/env python3
"""Add prev/next navigation links to all guide markdown files."""

import os

BASE = "/home/talaman/apps/positron_guide"

# Ordered list of (filename, display_title)
GUIDES = [
    ("heatset_insert_tool.md", "Heatset Insert Tool"),
    ("1_positron_3.2_extruder.md", "1 - Extruder"),
    ("2_positron_v32_z-column.md", "2 - Z Column"),
    ("3_positron_v32_z-drive.md", "3 - Z Drive"),
    ("4_positron_v32_bed-v-holder.md", "4 - Bed V-Holder"),
    ("5_positron_v32_touch-panel.md", "5 - Touch Panel"),
    ("6_positron_v32_toolhead.md", "6 - Toolhead"),
    ("7_positron_v32_spool-holder.md", "7 - Spool Holder"),
    ("8_positron_v32_base-plate.md", "8 - Base Plate"),
    ("9_positron_v32_final-assembly.md", "9 - Final Assembly"),
    ("10_positron_v32_folding.md", "10 - Folding"),
]


def build_nav(idx):
    """Build navigation line for guide at given index."""
    parts = []
    if idx > 0:
        prev_fn, prev_title = GUIDES[idx - 1]
        parts.append(f"[{prev_title}]({prev_fn})")
    if idx < len(GUIDES) - 1:
        next_fn, next_title = GUIDES[idx + 1]
        parts.append(f"[{next_title}]({next_fn})")

    if not parts:
        return ""

    if idx > 0 and idx < len(GUIDES) - 1:
        return f"**Previous:** {parts[0]} &nbsp;|&nbsp; **Next:** {parts[1]}"
    elif idx > 0:
        return f"**Previous:** {parts[0]}"
    else:
        return f"**Next:** {parts[0]}"


def main():
    for idx, (filename, title) in enumerate(GUIDES):
        filepath = os.path.join(BASE, filename)
        with open(filepath) as f:
            content = f.read()

        nav = build_nav(idx)
        if not nav:
            print(f"  SKIP {filename} (no neighbors)")
            continue

        # Remove existing nav if re-running
        content = content.strip()
        if nav in content:
            # Remove old nav lines
            lines = content.split("\n")
            lines = [l for l in lines if l != nav]
            content = "\n".join(lines).strip()

        # Add nav at top (after title block, before first ##)
        # Find position after the blockquote link line
        nav_top = f"\n---\n{nav}\n"
        nav_bottom = f"\n---\n{nav}\n"

        # Insert top nav after the "> Original:" blockquote
        orig_idx = content.find("> Original:")
        if orig_idx != -1:
            # Find end of that line
            line_end = content.find("\n", orig_idx)
            content = content[: line_end + 1] + nav_top + content[line_end + 1 :]

        # Add bottom nav
        content = content.rstrip() + nav_bottom

        with open(filepath, "w") as f:
            f.write(content)

        print(f"  OK {filename}")


if __name__ == "__main__":
    main()
