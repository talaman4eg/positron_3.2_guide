#!/usr/bin/env python3
"""Extract guide content from HTML, download images, generate clean markdown."""
import re, os, sys, json, urllib.parse, subprocess
from html import unescape
from pathlib import Path

BASE = Path('/home/talaman/apps/positron_guide')
IMG_DIR = BASE / 'img'
HTML_DIR = BASE / 'md_raw'

GUIDES = [
    ('2', 'z-column'),
    ('3', 'z-drive'),
    ('4', 'bed-v-holder'),
    ('5', 'touch-panel'),
    ('6', 'toolhead'),
    ('7', 'spool-holder'),
    ('8', 'base-plate'),
    ('9', 'final-assembly'),
    ('10', 'folding'),
    ('heatset', 'heatset-insert-tool'),
]

def decode_url(e):
    return urllib.parse.unquote(e.replace('&amp;', '&'))

def extract_from_html(html):
    """Extract structured data from HTML using the embedded JSON."""
    result = {
        'title': '',
        'description': '',
        'sections': [],
    }

    # Title from <title> tag
    m = re.search(r'<title>([^|]+)\|', html)
    if m:
        result['title'] = m.group(1).strip()

    # Description - first paragraph after h1
    # Look for the paragraph in the main content area
    idx = html.find('product-description-text')
    if idx >= 0:
        chunk = html[idx:idx+5000]
        # Find paragraph text
        for m in re.finditer(r'<p[^>]*>(.*?)</p>', chunk, re.DOTALL):
            t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            t = re.sub(r'\s+', ' ', t)
            # Clean up navigation artifacts
            t = re.sub(r'^(Contact\s+Us|Products|Makers|Guides|Search|Events|Resellers|News\s*&\s*Updates)\d*', '', t)
            t = t.strip()
            if len(t) > 30 and 'guide' in t.lower():
                result['description'] = t
                break

    # Extract sections, subsections, steps from rendered HTML
    # Sections: h2 with text-3xl
    # Subsections: h3 with text-2xl
    # Steps: paragraphs between subsection markers
    # Images: img tags with srcSet

    # Find all structural elements with positions
    elements = []

    for m in re.finditer(r'<h2[^>]*class="[^"]*text-3xl[^"]*"[^>]*>(.*?)</h2>', html, re.DOTALL):
        t = unescape(re.sub(r'<[^>]+>', '', m.group(1)).strip())
        elements.append(('h2', re.sub(r'\s+', ' ', t), m.start()))

    for m in re.finditer(r'<h3[^>]*class="[^"]*text-2xl[^"]*"[^>]*>(.*?)</h3>', html, re.DOTALL):
        t = unescape(re.sub(r'<[^>]+>', '', m.group(1)).strip())
        elements.append(('h3', re.sub(r'\s+', ' ', t), m.start()))

    # Find step text paragraphs - look for paragraphs with meaningful content
    # between h3 markers. Use [^<]* to avoid spanning across nested tags.
    for m in re.finditer(r'<p[^>]*>(.*?)</p>', html, re.DOTALL):
        inner = m.group(1)
        # Extract only direct text nodes, not nested element content
        # Split by < to get text between tags, join them
        parts = re.split(r'<[^>]*>', inner)
        t = ' '.join(p.strip() for p in parts if p.strip())
        t = re.sub(r'\s+', ' ', t).strip()
        # Filter meaningful step text
        if len(t) > 15 and not any(s in t.lower() for s in [
            r'image\(s\)', 'click to view', 'referenced by step',
            'back to top', 'precision motion', 'step images',
            'ldo motion', 'search', 'products', 'makers', 'guides',
            'news', 'resellers', 'events', 'contact us', 'about us',
            'contents', 'cookie', r'© 2026'
        ]) and not re.match(r'^step \d+ of \d+', t.lower()):
            elements.append(('p', t, m.start()))

    # Find images - handle any attribute order
    for m in re.finditer(r'<img[^>]*>', html, re.DOTALL):
        tag = m.group(0)
        alt_m = re.search(r'alt="([^"]*)"', tag)
        srcset_m = re.search(r'srcSet="([^"]*)"', tag)
        if not srcset_m:
            continue
        urls = re.findall(r'url=([^&\s"]+)', srcset_m.group(1))
        if urls:
            url = decode_url(urls[0])
            if 'ldomotion/media' in url:
                fn = url.split('media/')[-1]
                elements.append(('img', {'alt': alt_m.group(1) if alt_m else '', 'url': url, 'fn': fn}, m.start()))

    elements.sort(key=lambda x: x[2])

    # Build structure
    current_section = None
    current_sub = None
    pending_steps = []
    pending_images = []

    for etype, etext, _ in elements:
        if etype == 'h2':
            # Flush pending
            if current_sub and pending_steps:
                current_sub['steps'] = pending_steps[:]
                pending_steps = []
            if current_section and pending_images:
                if current_sub:
                    current_sub.setdefault('sub_images', []).extend(pending_images[:])
                else:
                    current_section.setdefault('intro_images', []).extend(pending_images[:])
                pending_images = []

            current_section = {'title': etext, 'subsections': []}
            result['sections'].append(current_section)
            current_sub = None

        elif etype == 'h3' and current_section:
            # Flush pending to previous sub
            if current_sub and pending_steps:
                current_sub['steps'] = pending_steps[:]
                pending_steps = []
            if pending_images:
                if current_sub:
                    current_sub.setdefault('sub_images', []).extend(pending_images[:])
                pending_images = []

            current_sub = {'title': etext, 'steps': []}
            current_section['subsections'].append(current_sub)

        elif etype == 'p':
            # Skip intro/description text
            if 'before you' in etext.lower() or 'please make sure' in etext.lower():
                continue
            if 'for all the m2.5' in etext.lower():
                continue
            pending_steps.append(etext)

        elif etype == 'img':
            pending_images.append(etext)

    # Flush remaining
    if current_sub and pending_steps:
        current_sub['steps'] = pending_steps[:]
    if pending_images and current_sub:
        current_sub.setdefault('sub_images', []).extend(pending_images[:])

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
            for img in sub.get('sub_images', []):
                fn = img['fn'].replace(' ', '%20')
                # fn already ends in .webp, so preview is fn.replace('.webp', '.preview.webp')
                preview_fn = fn.replace('.webp', '.preview.webp')
                md += f"  - [Preview](img/{num}/{preview_fn}) [Large](img/{num}/{fn})\n"
            md += "\n"

    return md

def main():
    for num, slug in GUIDES:
        html_file = HTML_DIR / f"{num}.html"
        if not html_file.exists():
            print(f"SKIP {num}: not found")
            continue

        print(f"Guide {num}: {slug}")
        with open(html_file) as f:
            html = f.read()

        data = extract_from_html(html)
        print(f"  Title: {data['title']}")
        print(f"  Sections: {len(data['sections'])}")

        # Count images and steps
        all_imgs = []
        total_steps = 0
        for sec in data['sections']:
            for sub in sec['subsections']:
                all_imgs.extend(sub.get('sub_images', []))
                total_steps += len(sub.get('steps', []))
        print(f"  Steps: {total_steps}, Images: {len(all_imgs)}")

        # Download images
        dl = download_images(all_imgs, num)
        print(f"  Downloaded: {dl} new images")

        # Generate markdown
        md = gen_markdown(data, num)
        if num == 'heatset':
            out = BASE / 'heatset_insert_tool.md'
        else:
            out = BASE / f"{num}_positron_v32_{slug}.md"
        with open(out, 'w') as f:
            f.write(md)
        print(f"  Written: {out.name}")

        # Save debug JSON
        with open(BASE / f"{num}_debug.json", 'w') as f:
            json.dump(data, f, indent=2)

        print()

if __name__ == '__main__':
    main()
