#!/usr/bin/env python3
"""Process markdown content from LDO Motion guides, download images, generate clean markdown."""
import re, os, sys, urllib.parse, subprocess
from pathlib import Path

BASE = Path('/home/talaman/apps/positron_guide')
IMG_DIR = BASE / 'img'
MD_DIR = BASE / 'md_raw'

GUIDES = [
    ('2', 'z-column', 'https://ldomotion.com/guides/2---positron-v32---z-column'),
    ('3', 'z-drive', 'https://ldomotion.com/guides/3---positron-v32---z-drive'),
    ('4', 'bed-v-holder', 'https://ldomotion.com/guides/4---positron-v32---bed-v-holder'),
    ('5', 'touch-panel', 'https://ldomotion.com/guides/5---positron-v32---touch-panel'),
    ('6', 'toolhead', 'https://ldomotion.com/guides/6---positron-v32---toolhead'),
    ('7', 'spool-holder', 'https://ldomotion.com/guides/7---positron-v32---spool-holder'),
    ('8', 'base-plate', 'https://ldomotion.com/guides/8---positron-v32---base-plate'),
    ('9', 'final-assembly', 'https://ldomotion.com/guides/9---positron-v32---final-assembly'),
    ('10', 'folding', 'https://ldomotion.com/guides/10---positron-v32---folding'),
    ('heatset', 'heatset-insert-tool', 'https://ldomotion.com/guides/heatset-insert-tool-guide'),
]

def decode_url(encoded):
    return urllib.parse.unquote(encoded.replace('&amp;', '&'))

def extract_s3_url(md_link):
    """Extract S3 URL from markdown image link like ![alt](/_next/image?url=...)"""
    m = re.search(r'\]\(/_next/image\?url=([^)]+)\)', md_link)
    if m:
        return decode_url(m.group(1))
    return None

def process_markdown(md_content, num, slug):
    """Parse the raw markdown content and return structured data."""
    result = {
        'title': '',
        'description': '',
        'sections': [],  # [{title, subsections: [{title, steps: [{text, images: []}]}]}]
    }

    lines = md_content.split('\n')

    # Extract title
    for line in lines:
        if line.startswith('# ') and not line.startswith('## '):
            result['title'] = line[2:].strip()
            break

    # Find description (first paragraph after title, before Contents)
    in_title = False
    desc_found = False
    for line in lines:
        if line.startswith('# '):
            in_title = True
            continue
        if in_title and line.strip() and not line.startswith('#') and not line.startswith('[') and not line.startswith('!'):
            result['description'] = line.strip()
            desc_found = True
            break
        if line.startswith('## Contents'):
            break

    # Parse sections and subsections
    current_section = None
    current_sub = None
    current_step = None
    in_step_images = False
    step_images = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Section heading: ## 1. Parts to Print
        m = re.match(r'^## (\d+\.\s+.+)$', line)
        if m:
            current_section = {'title': m.group(1).strip(), 'subsections': []}
            result['sections'].append(current_section)
            current_sub = None
            in_step_images = False
            step_images = []
            i += 1
            continue

        # Subsection heading: ### Printed Parts
        m = re.match(r'^### (.+)$', line)
        if m:
            # Flush current step
            if current_step and current_sub:
                current_step['images'] = step_images[:]
                current_sub['steps'].append(current_step)
                current_step = None
                step_images = []

            current_sub = {'title': m.group(1).strip(), 'steps': []}
            if current_section:
                current_section['subsections'].append(current_sub)
            in_step_images = False
            i += 1
            continue

        # Step Images header
        if line.strip() == '#### Step Images':
            # Flush current step
            if current_step and current_sub:
                current_step['images'] = step_images[:]
                current_sub['steps'].append(current_step)
                current_step = None
                step_images = []
            in_step_images = True
            i += 1
            continue

        # Image line: ![alt](url)
        if in_step_images and line.strip().startswith('!['):
            s3_url = extract_s3_url(line.strip())
            if s3_url:
                fn = s3_url.split('media/')[-1]
                step_images.append({'alt': line.strip()[:20], 'url': s3_url, 'fn': fn})
            i += 1
            continue

        # "Referenced by step N" or "1 image(s) - Click to view" - skip
        if 'Referenced by step' in line or 'image(s) - Click to view' in line:
            i += 1
            continue

        # Step number line like "1" or "23" - skip
        if re.match(r'^\d+$', line.strip()) and len(line.strip()) <= 3:
            i += 1
            continue

        # "Step N of M in this section" - skip
        if 'Step ' in line and 'of ' in line and 'in this section' in line:
            i += 1
            continue

        # Navigation/footer content - skip
        if any(skip in line for skip in ['Back to Top', 'LDO Motion Logo', 'Products', 'Makers', 'Guides', 'News', 'Resellers', 'Events', 'Contact Us', 'About Us', '© 2026']):
            i += 1
            continue

        # Link lines like [text](url) - skip
        if re.match(r'^\[.*\]\(.*\)$', line.strip()):
            i += 1
            continue

        # Empty lines
        if not line.strip():
            if in_step_images:
                in_step_images = False
            i += 1
            continue

        # Regular text line - this is step content
        text = line.strip()
        if text and current_sub and not in_step_images:
            if not current_step:
                current_step = {'text': text, 'images': []}
            else:
                current_step['text'] += ' ' + text
        elif text and current_section and not current_sub:
            # Text in section but before subsections (intro text)
            pass

        i += 1

    # Flush last step
    if current_step and current_sub:
        current_step['images'] = step_images[:]
        current_sub['steps'].append(current_step)

    return result

def download_image(url, dest_path):
    """Download a single image (large + preview)."""
    fn = url.split('media/')[-1]
    encoded = fn.replace(' ', '%20')
    s3_url = f"https://s3.ldomotion.com/ldomotion/media/{encoded}"

    if dest_path.exists():
        return False  # Already exists

    try:
        subprocess.run(['curl', '-sL', '-o', str(dest_path), s3_url],
                       check=True, timeout=30, capture_output=True)
        # Preview
        preview_path = Path(str(dest_path).replace('.webp', '.preview.webp'))
        preview_url = f"https://ldomotion.com/_next/image?url={urllib.parse.quote(url, safe='')}&w=640&q=75"
        subprocess.run(['curl', '-sL', '-o', str(preview_path), preview_url],
                       check=True, timeout=30, capture_output=True)
        return True
    except Exception as e:
        print(f"  ERROR: {fn}: {e}")
        return False

def gen_markdown(data, num):
    """Generate clean markdown from structured data."""
    md = f"# {data['title']}\n\n"
    if data['description']:
        md += f"{data['description']}\n\n"

    for sec in data['sections']:
        md += f"## {sec['title']}\n\n"
        for sub in sec['subsections']:
            md += f"### {sub['title']}\n\n"
            # Collect all images for this subsection
            all_sub_images = []
            for step in sub['steps']:
                all_sub_images.extend(step.get('images', []))

            for step in sub['steps']:
                md += f"- {step['text']}\n"
                for img in step.get('images', []):
                    fn = img['fn'].replace(' ', '%20')
                    md += f"  - [Preview](img/{num}/{fn}.preview.webp) [Large](img/{num}/{fn}.webp)\n"

            # If no steps had images but subsection has images, add them at end
            if not all_sub_images and sub.get('images'):
                for img in sub['images']:
                    fn = img['fn'].replace(' ', '%20')
                    md += f"  - [Preview](img/{num}/{fn}.preview.webp) [Large](img/{num}/{fn}.webp)\n"

            md += "\n"

    return md

def main():
    import json

    # Read raw markdown files
    for num, slug, url in GUIDES:
        md_file = MD_DIR / f"{num}.md"
        if not md_file.exists():
            print(f"SKIP {num}: {md_file} not found")
            continue

        print(f"Processing guide {num}: {slug}...")
        with open(md_file) as f:
            content = f.read()

        data = process_markdown(content, num, slug)
        print(f"  Title: {data['title']}")
        print(f"  Sections: {len(data['sections'])}")

        # Collect all images
        all_images = []
        for sec in data['sections']:
            for sub in sec['subsections']:
                for step in sub['steps']:
                    all_images.extend(step.get('images', []))

        print(f"  Total images: {len(all_images)}")
        print(f"  Total steps: {sum(len(sub['steps']) for sec in data['sections'] for sub in sec['subsections'])}")

        # Download images
        img_dir = IMG_DIR / num
        img_dir.mkdir(parents=True, exist_ok=True)

        dl_count = 0
        for img in all_images:
            fn = img['fn']
            dest = img_dir / fn
            if download_image(img['url'], dest):
                dl_count += 1
        print(f"  Downloaded: {dl_count} new images")

        # Generate markdown
        md = gen_markdown(data, num)
        out_file = BASE / f"{num}_positron_v32_{slug}.md" if num != 'heatset' else BASE / f"heatset_insert_tool.md"
        with open(out_file, 'w') as f:
            f.write(md)
        print(f"  Written: {out_file.name}")

        # Save structured data for debugging
        json_file = BASE / f"{num}_data.json"
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=2)

        print()

if __name__ == '__main__':
    MD_DIR.mkdir(parents=True, exist_ok=True)
    main()
