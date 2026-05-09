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
    parts = ["**Index:** [README](README.md)"]
    if idx > 0:
        prev_fn, prev_title = GUIDES[idx - 1]
        parts.append(f"**Previous:** [{prev_title}]({prev_fn})")
    if idx < len(GUIDES) - 1:
        next_fn, next_title = GUIDES[idx + 1]
        parts.append(f"**Next:** [{next_title}]({next_fn})")

    return " &nbsp;|&nbsp; ".join(parts)


def strip_old_nav(content):
    """Remove existing nav blocks (--- + nav line)."""
    import re
    # Remove --- + nav line blocks (handle possible doubled ---)
    content = re.sub(r'\n---\n(?:---\n)?\*\*Index:\*\*.+?\n', '\n', content)
    content = re.sub(r'\n---\n(?:---\n)?\*\*Previous:\*\*.+?\n', '\n', content)
    content = re.sub(r'\n---\n(?:---\n)?\*\*Next:\*\*.+?\n', '\n', content)
    # Remove bare nav lines without ---
    content = re.sub(r'\n\[Index\]\(README\.md\).+?\n', '\n', content)
    # Clean up orphaned --- separators (--- surrounded by blank lines)
    content = re.sub(r'\n\n---\n\n', '\n\n', content)
    # Clean up multiple consecutive blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()


def main():
    for idx, (filename, title) in enumerate(GUIDES):
        filepath = os.path.join(BASE, filename)
        with open(filepath) as f:
            content = f.read()

        nav = build_nav(idx)

        # Remove existing nav blocks if re-running
        content = strip_old_nav(content)

        # Add nav at top after the "> Original:" blockquote
        nav_block = f"\n---\n{nav}\n"

        orig_idx = content.find("> Original:")
        if orig_idx != -1:
            line_end = content.find("\n", orig_idx)
            content = content[: line_end + 1] + nav_block + content[line_end + 1 :]

        # Add bottom nav (ensure blank line before separator)
        content = content.rstrip()
        if not content.endswith("\n"):
            content += "\n"
        content += f"---\n{nav}\n"

        with open(filepath, "w") as f:
            f.write(content)

        print(f"  OK {filename}")


if __name__ == "__main__":
    main()
