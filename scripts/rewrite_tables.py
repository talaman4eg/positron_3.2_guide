#!/usr/bin/env python3
"""Rewrite all guide markdown files with 2-column image tables.

Parses original HTML to get correct image-to-step mapping,
then generates markdown with images in 2-column tables after
the text they refer to.
"""

import re
import os
import html as htmlmod
from urllib.parse import unquote

BASE = "/home/talaman/apps/positron_guide"
MD_RAW = f"{BASE}/md_raw"

GUIDE_MAP = {
    "1.html": ("1_positron_3.2_extruder.md", "1", "https://ldomotion.com/guides/1---positron-v32---extruder"),
    "2.html": ("2_positron_v32_z-column.md", "2", "https://ldomotion.com/guides/2---positron-v32---z-column"),
    "3.html": ("3_positron_v32_z-drive.md", "3", "https://ldomotion.com/guides/3---positron-v32---z-drive"),
    "4.html": ("4_positron_v32_bed-v-holder.md", "4", "https://ldomotion.com/guides/4---positron-v32---bed-v-holder"),
    "5.html": ("5_positron_v32_touch-panel.md", "5", "https://ldomotion.com/guides/5---positron-v32---touch-panel"),
    "6.html": ("6_positron_v32_toolhead.md", "6", "https://ldomotion.com/guides/6---positron-v32---toolhead"),
    "7.html": ("7_positron_v32_spool-holder.md", "7", "https://ldomotion.com/guides/7---positron-v32---spool-holder"),
    "8.html": ("8_positron_v32_base-plate.md", "8", "https://ldomotion.com/guides/8---positron-v32---base-plate"),
    "9.html": ("9_positron_v32_final-assembly.md", "9", "https://ldomotion.com/guides/9---positron-v32---final-assembly"),
    "10.html": ("10_positron_v32_folding.md", "10", "https://ldomotion.com/guides/10---positron-v32---folding"),
    "heatset.html": ("heatset_insert_tool.md", "heatset", "https://ldomotion.com/guides/heatset-insert-tool-guide"),
}


def s3_to_filename(s3_path):
    """Convert S3 image path to local filename."""
    filename = s3_path.split("/")[-1]
    filename = unquote(filename)
    filename = filename.replace(".webp", "")
    # Lowercase, replace spaces/special chars with dashes
    filename = filename.lower().strip()
    filename = re.sub(r"[^\w\-]", "-", filename)
    filename = re.sub(r"-+", "-", filename)
    filename = filename.strip("-")
    return filename


def extract_wrapper_content(raw, wrapper_match):
    """Extract content from a section wrapper div."""
    start = wrapper_match.start()
    depth = 1
    pos = start + len(wrapper_match.group())
    while depth > 0 and pos < len(raw):
        if pos > 0 and raw[pos - 5 : pos] == "<div ":
            depth += 1
        elif raw[pos : pos + 6] == "</div>":
            depth -= 1
        pos += 1
    return raw[start:pos]


def extract_steps(left_panel):
    """Extract step text blocks from left panel."""
    steps = []
    text_blocks = list(
        re.finditer(
            r'<div class="[^"]*product-description-text[^"]*"[^>]*>(.*?)</div>',
            left_panel,
            re.DOTALL,
        )
    )
    for tb in text_blocks:
        block = tb.group(1)
        p_match = re.search(r"<p[^>]*>(.*?)</p>", block, re.DOTALL)
        if p_match:
            text = re.sub(r"<[^>]+>", "", p_match.group(1)).strip()
            text = htmlmod.unescape(text)
            steps.append(text)
    return steps


def extract_images(right_panel):
    """Extract image cards with step references from right panel."""
    images = []
    # Find cards - each card is a div with 'relative group' class
    cards = list(re.finditer(r'<div class="relative group[^"]*">', right_panel))

    for ci, card in enumerate(cards):
        if ci + 1 < len(cards):
            card_content = right_panel[card.start() : cards[ci + 1].start()]
        else:
            card_content = right_panel[card.start() : card.start() + 5000]

        # Extract image URL
        img_match = re.search(r'srcSet="([^"]+)"', card_content)
        if img_match:
            url_match = re.search(r"url=([^&\"]+)", img_match.group(1))
            if url_match:
                url = unquote(url_match.group(1))
                filename = s3_to_filename(url)
            else:
                continue
        else:
            continue

        # Extract step reference
        ref_match = re.search(r"Referenced by step <!-- -->(\d+)", card_content)
        step_ref = int(ref_match.group(1)) if ref_match else None

        images.append({"filename": filename, "step": step_ref})

    return images


def images_to_table(img_filenames, img_dir):
    """Generate a 2-column markdown table from image filenames."""
    if not img_filenames:
        return ""

    lines = ["| | |", "|:-:|:-:|"]
    for i in range(0, len(img_filenames), 2):
        fn1 = img_filenames[i]
        cell1 = f"[![{fn1}](img/{img_dir}/{fn1}.preview.png)](img/{img_dir}/{fn1}.png)"
        if i + 1 < len(img_filenames):
            fn2 = img_filenames[i + 1]
            cell2 = f"[![{fn2}](img/{img_dir}/{fn2}.preview.png)](img/{img_dir}/{fn2}.png)"
        else:
            cell2 = ""
        lines.append(f"| {cell1} | {cell2} |")

    return "\n".join(lines)


def process_guide(html_file, md_file, img_dir, original_url):
    """Process a single guide HTML file and generate markdown."""
    html_path = f"{MD_RAW}/{html_file}"
    if not os.path.exists(html_path):
        print(f"  SKIP: {html_path} not found")
        return False

    with open(html_path) as f:
        raw = f.read()

    lines = []

    # Extract h1 title
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.DOTALL)
    if h1_match:
        title = re.sub(r"<[^>]+>", "", h1_match.group(1)).strip()
        title = htmlmod.unescape(title)
        lines.append(f"# {title}")

    # Extract summary text from the same div as h1 (mb-8 container)
    h1_start = h1_match.start() if h1_match else 0
    # Find the opening <div class="mb-8"> that contains the h1
    mb8_start = raw.rfind('<div class="mb-8"', 0, h1_start)
    if mb8_start == -1:
        mb8_start = raw.rfind('<div class="mb-12"', 0, h1_start)
    if mb8_start != -1:
        # Find the closing </div> for this container
        mb8_depth = 1
        mb8_pos = mb8_start + len('<div class="mb-8"')
        # Skip to end of opening tag
        tag_end = raw.index(">", mb8_start) + 1
        mb8_pos = tag_end
        while mb8_depth > 0 and mb8_pos < len(raw):
            if raw[mb8_pos : mb8_pos + 5] == "<div ":
                mb8_depth += 1
            elif raw[mb8_pos : mb8_pos + 6] == "</div>":
                mb8_depth -= 1
            mb8_pos += 1
        mb8_content = raw[mb8_start:mb8_pos]
        # Extract product-description-text from this container (excluding h1)
        summary_matches = re.findall(
            r'<div class="[^"]*product-description-text[^"]*"[^>]*>(.*?)</div>',
            mb8_content,
            re.DOTALL,
        )
        for sm in summary_matches:
            text = re.sub(r"<[^>]+>", "", sm).strip()
            text = htmlmod.unescape(text)
            if text:
                lines.append(f"{text}")
    lines.append("")

    # Original link
    lines.append(f"> Original: [LDO Motion Guide]({original_url})")

    # Find section wrappers
    wrappers = list(
        re.finditer(r'<div class="flex flex-col xl:flex-row min-h-\[400px\]">', raw)
    )

    # Process h2 sections
    h2s = list(re.finditer(r"<h2[^>]*>(.*?)</h2>", raw, re.DOTALL))
    h3s = list(re.finditer(r"<h3[^>]*>(.*?)</h3>", raw, re.DOTALL))

    for hi, h2 in enumerate(h2s):
        h2_text = re.sub(r"<[^>]+>", "", h2.group(1)).strip()
        h2_text = htmlmod.unescape(h2_text)
        if h2_text == "Contents":
            continue  # Skip table of contents

        lines.append(f"\n## {h2_text}")

        # Find intro text between this h2 and the first wrapper after it
        next_wrappers = [w for w in wrappers if w.start() > h2.end()]
        if next_wrappers:
            intro_area = raw[h2.end() : next_wrappers[0].start()]
        else:
            intro_area = ""

        intro_texts = re.findall(
            r'<div class="[^"]*product-description-text[^"]*"[^>]*>(.*?)</div>',
            intro_area,
            re.DOTALL,
        )
        for it in intro_texts:
            text = re.sub(r"<[^>]+>", "", it).strip()
            text = htmlmod.unescape(text)
            if text:
                lines.append(f"\n> {text}")

        # Process wrappers (subsection) that belong to this h2
        # Find h3s that are between this h2 and the next h2
        next_h2 = h2s[hi + 1].start() if hi + 1 < len(h2s) else len(raw)
        section_h3s = [h for h in h3s if h2.end() < h.start() < next_h2]

        # Find wrappers that belong to this h2 section
        section_wrappers = [w for w in wrappers if h2.end() < w.start() < next_h2]

        # Also find h3s that don't have a corresponding wrapper (text-only subsections)
        wrapper_h3_positions = set()
        for w in section_wrappers:
            for h in reversed(section_h3s):
                if h.end() < w.start():
                    # Check no other h3 is between this h3 and the wrapper
                    intervening = [
                        hh
                        for hh in section_h3s
                        if h.end() < hh.start() < w.start()
                    ]
                    if not intervening:
                        wrapper_h3_positions.add(h.start())
                        break

        for wi, w in enumerate(section_wrappers):
            # Find the h3 heading for this wrapper
            preceding_h3 = None
            for h in reversed(section_h3s):
                if h.end() < w.start():
                    preceding_h3 = h
                    break

            if preceding_h3:
                h3_text = re.sub(r"<[^>]+>", "", preceding_h3.group(1)).strip()
                h3_text = htmlmod.unescape(h3_text)
                lines.append(f"\n### {h3_text}")

            # Extract wrapper content
            w_content = extract_wrapper_content(raw, w)

            # Extract left panel (steps)
            left_match = re.search(
                r'<div class="flex-1 p-6 xl:pr-3">(.*?)</div>\s*<div class="flex-1 xl:w-1/2',
                w_content,
                re.DOTALL,
            )
            if not left_match:
                continue

            steps = extract_steps(left_match.group(1))

            # Extract right panel (images)
            right_match = re.search(
                r'<div class="flex-1 xl:w-1/2 p-6 xl:pl-3', w_content, re.DOTALL
            )
            images = []
            if right_match:
                right_content = w_content[right_match.start() :]
                images = extract_images(right_content)

            # Map images to steps
            step_images = {}  # step_number (1-based) -> [filenames]
            unreferenced = []  # images without step reference

            for img in images:
                if img["step"] is not None:
                    step_num = img["step"]
                    if step_num not in step_images:
                        step_images[step_num] = []
                    step_images[step_num].append(img["filename"])
                else:
                    unreferenced.append(img["filename"])

            # Output steps as list
            for si, step_text in enumerate(steps):
                lines.append(f"- {step_text}")

            # Collect all images in order: referenced first (by step order), then unreferenced
            all_imgs = []
            for si in range(len(steps)):
                step_num = si + 1
                if step_num in step_images:
                    all_imgs.extend(step_images[step_num])
            all_imgs.extend(unreferenced)

            # One consolidated table per subsection
            if all_imgs:
                table = images_to_table(all_imgs, img_dir)
                if table:
                    lines.append(f"\n{table}")

        # Handle h3s without wrappers (text-only subsections)
        for h in section_h3s:
            if h.start() not in wrapper_h3_positions:
                h3_text = re.sub(r"<[^>]+>", "", h.group(1)).strip()
                h3_text = htmlmod.unescape(h3_text)
                lines.append(f"\n### {h3_text}")

                # Find text between this h3 and the next h3 or wrapper
                next_items = [hh.start() for hh in section_h3s if hh.start() > h.start()]
                next_items += [ww.start() for ww in section_wrappers if ww.start() > h.start()]
                next_items += [next_h2]
                end_pos = min(next_items) if next_items else next_h2

                text_area = raw[h.end():end_pos]
                text_blocks = re.findall(
                    r'<div class="[^"]*product-description-text[^"]*"[^>]*>(.*?)</div>',
                    text_area,
                    re.DOTALL,
                )
                for tb in text_blocks:
                    text = re.sub(r"<[^>]+>", "", tb).strip()
                    text = htmlmod.unescape(text)
                    if text:
                        lines.append(f"- {text}")

    md_path = f"{BASE}/{md_file}"
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"  OK: {md_file} ({len(lines)} lines)")
    return True


def main():
    for html_file, (md_file, img_dir, original_url) in GUIDE_MAP.items():
        print(f"Processing {html_file} -> {md_file}")
        process_guide(html_file, md_file, img_dir, original_url)


if __name__ == "__main__":
    main()
