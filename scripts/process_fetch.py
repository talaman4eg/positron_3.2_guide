#!/usr/bin/env python3
"""Extract guide content from webfetch markdown, download images, generate clean markdown."""
import re, os, sys, json, urllib.parse, subprocess
from pathlib import Path

BASE = Path('/home/talaman/apps/positron_guide')
IMG_DIR = BASE / 'img'
FETCH_DIR = BASE / 'md_fetch'

GUIDES = [
    ('8', 'base-plate'),
    ('9', 'final-assembly'),
    ('10', 'folding'),
    ('heatset', 'heatset-insert-tool'),
]

def extract_images_from_url(url):
    """Extract filename from a Next.js image URL."""
    m = re.search(r'url=([^&]+)', url)
    if not m:
        return None
    decoded = urllib.parse.unquote(m.group(1))
    if 'ldomotion/media' not in decoded:
        return None
    fn = decoded.split('media/')[-1]
    return fn, decoded

def parse_fetch_markdown(text):
    """Parse webfetch markdown output into structured data."""
    result = {
        'title': '',
        'description': '',
        'sections': [],
    }

    lines = text.split('\n')
    i = 0

    # Extract title
    for line in lines:
        m = re.match(r'^# (.+)$', line.strip())
        if m:
            result['title'] = m.group(1).strip()
            break

    # Extract description: first paragraph after title, before ## Contents
    in_title = False
    desc_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('# '):
            if in_title:
                break
            in_title = True
            continue
        if in_title:
            if stripped.startswith('##') or stripped.startswith('['):
                break
            if stripped and not stripped.startswith('![') and not stripped.startswith('['):
                desc_lines.append(stripped)

    # Join description, skip nav items
    desc = ' '.join(desc_lines)
    # Filter out nav text
    nav_words = ['products', 'makers', 'guides', 'news', 'resellers', 'events', 'search', 'contact']
    clean_parts = []
    for part in desc.split('. '):
        if not any(w in part.lower() for w in nav_words):
            clean_parts.append(part)
    result['description'] = '. '.join(clean_parts).strip('.')

    # Parse sections and subsections
    current_section = None
    current_sub = None
    pending_steps = []
    in_step_images = False
    step_images = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Section heading: ## N. Section Name
        m = re.match(r'^##\s+\d+\.\s+(.+)$', stripped)
        if m and not stripped.startswith('## Contents'):
            # Flush pending
            if current_sub and pending_steps:
                current_sub['steps'] = pending_steps[:]
                pending_steps = []
            if step_images and current_sub:
                current_sub.setdefault('images', []).extend(step_images[:])
                step_images = []

            current_section = {'title': m.group(1).strip(), 'subsections': []}
            result['sections'].append(current_section)
            current_sub = None
            in_step_images = False
            i += 1
            continue

        # Skip Contents section
        if stripped.startswith('## Contents'):
            in_step_images = False
            i += 1
            continue

        # Subsection heading: ### Subsection Name
        m = re.match(r'^### (.+)$', stripped)
        if m:
            # Flush pending
            if current_sub and pending_steps:
                current_sub['steps'] = pending_steps[:]
                pending_steps = []
            if step_images and current_sub:
                current_sub.setdefault('images', []).extend(step_images[:])
                step_images = []

            if current_section:
                current_sub = {'title': m.group(1).strip(), 'steps': []}
                current_section['subsections'].append(current_sub)
            in_step_images = False
            i += 1
            continue

        # Step Images section
        if stripped == '#### Step Images':
            in_step_images = True
            i += 1
            continue

        # Image lines: ![alt](url)
        if in_step_images:
            m = re.match(r'^!\[.*?\]\((.+)$', stripped)
            if m:
                img_url = m.group(1).strip()
                extracted = extract_images_from_url(img_url)
                if extracted:
                    fn, full_url = extracted
                    step_images.append({'fn': fn, 'url': full_url})
                i += 1
                continue
            # End of step images section if we hit a non-image line
            if stripped and not stripped.startswith('Referenced'):
                in_step_images = False

        # Skip noise
        if any(s in stripped.lower() for s in [
            'referenced by step', 'step \d+ of \d+', 'image\(s\)',
            'click to view', 'back to top', 'ldo motion',
            '© 2026', 'about us'
        ]):
            i += 1
            continue
        if stripped.startswith('[') or stripped.startswith('!['):
            i += 1
            continue
        # Skip numbered step markers (e.g., "1", "2" on their own line before a subsection)
        if re.match(r'^\d+$', stripped):
            i += 1
            continue

        # Step text: meaningful paragraph
        if stripped and current_sub and not in_step_images:
            # Skip "Before you start..." and "For all the M2.5..."
            lower = stripped.lower()
            if 'before you start to assemble' in lower:
                i += 1
                continue
            if 'for all the m2.5' in lower:
                i += 1
                continue
            if len(stripped) > 20:
                pending_steps.append(stripped)

        i += 1

    # Flush remaining
    if current_sub and pending_steps:
        current_sub['steps'] = pending_steps[:]
    if step_images and current_sub:
        current_sub.setdefault('images', []).extend(step_images[:])

    return result

def download_images(images, num):
    """Download all images for a guide."""
    img_dir = IMG_DIR / num
    img_dir.mkdir(parents=True, exist_ok=True)

    dl = 0
    seen = set()
    for img in images:
        fn = img['fn']
        if fn in seen:
            continue
        seen.add(fn)

        dest = img_dir / fn
        if dest.exists():
            continue

        encoded = fn.replace(' ', '%20')
        s3_url = f"https://s3.ldomotion.com/ldomotion/media/{encoded}"
        try:
            subprocess.run(['curl', '-sL', '-o', str(dest), s3_url],
                           check=True, timeout=30, capture_output=True)
            preview_path = img_dir / fn.replace('.webp', '.preview.webp')
            if not preview_path.exists():
                preview_url = f"https://ldomotion.com/_next/image?url={urllib.parse.quote(img['url'], safe='')}&w=640&q=75"
                subprocess.run(['curl', '-sL', '-o', str(preview_path), preview_url],
                               check=True, timeout=30, capture_output=True)
            dl += 1
        except Exception as e:
            print(f"  ERR: {fn}: {e}")

    return dl

def gen_markdown(data, num):
    """Generate clean markdown."""
    md = f"# {data['title']}\n\n"
    if data['description']:
        md += f"{data['description']}\n\n"

    for sec in data['sections']:
        md += f"## {sec['title']}\n\n"
        for sub in sec['subsections']:
            md += f"### {sub['title']}\n\n"
            for step in sub.get('steps', []):
                md += f"- {step}\n"
            for img in sub.get('images', []):
                fn = img['fn'].replace(' ', '%20')
                md += f"  - [Preview](img/{num}/{fn}.preview.webp) [Large](img/{num}/{fn}.webp)\n"
            md += "\n"

    return md

def main():
    for num, slug in GUIDES:
        fetch_file = FETCH_DIR / f"{num}.md"
        if not fetch_file.exists():
            print(f"SKIP {num}: fetch file not found at {fetch_file}")
            continue

        print(f"Guide {num}: {slug}")
        with open(fetch_file) as f:
            text = f.read()

        data = parse_fetch_markdown(text)
        print(f"  Title: {data['title']}")
        print(f"  Sections: {len(data['sections'])}")

        all_imgs = []
        total_steps = 0
        for sec in data['sections']:
            for sub in sec['subsections']:
                all_imgs.extend(sub.get('images', []))
                total_steps += len(sub.get('steps', []))
        print(f"  Steps: {total_steps}, Images: {len(all_imgs)}")

        dl = download_images(all_imgs, num)
        print(f"  Downloaded: {dl} new images")

        md = gen_markdown(data, num)
        if num == 'heatset':
            out = BASE / 'heatset_insert_tool.md'
        else:
            out = BASE / f"{num}_positron_v32_{slug}.md"
        with open(out, 'w') as f:
            f.write(md)
        print(f"  Written: {out.name}")

        with open(BASE / f"{num}_debug.json", 'w') as f:
            json.dump(data, f, indent=2)
        print()

if __name__ == '__main__':
    main()
