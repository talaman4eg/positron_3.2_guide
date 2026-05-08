#!/usr/bin/env python3
"""Extract guide content from HTML using product-description-text blocks."""
import re, json, urllib.parse, subprocess
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

SKIP_TEXTS = [
    'before you start to assemble', 'please make sure you have these parts printed',
    'for all the m2.5 screws', 'image(s)', 'click to view', 'referenced by step',
    'back to top', 'precision motion', 'step images', 'ldo motion',
    'search', 'products', 'makers', 'guides', 'news', 'resellers',
    'events', 'contact us', 'about us', 'contents', 'cookie', '© 2026',
]

def decode_url(e):
    return urllib.parse.unquote(e.replace('&amp;', '&'))

def find_matching_div(html, start):
    """Find the closing </div> that matches the opening <div> at position start."""
    depth = 1
    pos = start
    while pos < len(html) and depth > 0:
        if html[pos:pos+5] in ('<div ', '<div\n', '<div>') or html[pos:pos+4] == '<div':
            if pos + 4 < len(html) and html[pos+4] in (' ', '>', '\n', '/'):
                depth += 1
        if html[pos:pos+6] == '</div>':
            depth -= 1
            if depth == 0:
                return pos
        pos += 1
    return pos

def extract_from_html(html):
    result = {'title': '', 'description': '', 'sections': []}

    # Title
    m = re.search(r'<title>([^<]+)</title>', html)
    if m:
        result['title'] = m.group(1).strip().split(' | ')[0].strip()

    # Find all structural elements with positions
    elements = []

    # h2 sections (text-3xl)
    for m in re.finditer(r'<h2[^>]*class="[^"]*text-3xl[^"]*"[^>]*>(.*?)</h2>', html, re.DOTALL):
        # Only get direct text, not nested
        direct = re.sub(r'<[^>]+>', '', m.group(1))
        t = re.sub(r'\s+', ' ', direct).strip()
        if t and t != 'Contents':
            elements.append(('h2', t, m.start()))

    # h3 subsections (text-2xl)
    for m in re.finditer(r'<h3[^>]*class="[^"]*text-2xl[^"]*"[^>]*>(.*?)</h3>', html, re.DOTALL):
        direct = re.sub(r'<[^>]+>', '', m.group(1))
        t = re.sub(r'\s+', ' ', direct).strip()
        if t:
            elements.append(('h3', t, m.start()))

    # product-description-text blocks -> paragraphs
    for m in re.finditer(r'<div[^>]*product-description-text[^>]*>', html):
        block_start = m.end()
        block_end = find_matching_div(html, block_start)
        block = html[block_start:block_end]

        # Extract direct text from <p> tags (no nested elements)
        for pm in re.finditer(r'<p>([^<]*)</p>', block):
            t = pm.group(1).strip()
            if t and len(t) > 10:
                lower = t.lower()
                if not any(s in lower for s in SKIP_TEXTS):
                    elements.append(('p', t, m.start()))

    # Images from img tags with srcSet
    for m in re.finditer(r'<img[^>]*srcSet="([^"]*)"[^>]*>', html):
        srcset = m.group(1)
        urls = re.findall(r'url=([^&\s"]+)', srcset)
        if urls:
            url = decode_url(urls[0])
            if 'ldomotion/media' in url:
                fn = url.split('media/')[-1]
                # Get alt from the same tag
                alt_m = re.search(r'alt="([^"]*)"', html[max(0,m.start()-100):m.end()])
                alt = alt_m.group(1) if alt_m else ''
                elements.append(('img', {'alt': alt, 'url': url, 'fn': fn}, m.start()))

    elements.sort(key=lambda x: x[2])

    # Build structure
    current_section = None
    current_sub = None
    pending_steps = []
    pending_images = []

    for etype, etext, pos in elements:
        if etype == 'h2':
            if current_sub and pending_steps:
                current_sub['steps'] = pending_steps[:]
                pending_steps = []
            if current_section and pending_images:
                if current_sub:
                    current_sub.setdefault('images', []).extend(pending_images[:])
                else:
                    current_section.setdefault('intro_images', []).extend(pending_images[:])
                pending_images = []
            current_section = {'title': etext, 'subsections': []}
            result['sections'].append(current_section)
            current_sub = None

        elif etype == 'h3' and current_section:
            if current_sub and pending_steps:
                current_sub['steps'] = pending_steps[:]
                pending_steps = []
            if pending_images and current_sub:
                current_sub.setdefault('images', []).extend(pending_images[:])
                pending_images = []
            current_sub = {'title': etext, 'steps': []}
            current_section['subsections'].append(current_sub)

        elif etype == 'p':
            pending_steps.append(etext)

        elif etype == 'img':
            pending_images.append(etext)

    # Flush remaining
    if current_sub and pending_steps:
        current_sub['steps'] = pending_steps[:]
    if pending_images and current_sub:
        current_sub.setdefault('images', []).extend(pending_images[:])

    # Extract description and remove it from steps
    if not result['description']:
        for sec in result['sections']:
            for sub in sec['subsections']:
                for step in sub.get('steps', []):
                    lower = step.lower().strip()
                    if (lower.startswith('this guide') or lower.startswith('in this guide') or lower.startswith('brass inserts')) and len(step) > 50:
                        result['description'] = step
                        break
            if result['description']:
                break

    # Remove description duplicate from all subsection steps
    if result['description']:
        for sec in result['sections']:
            for sub in sec['subsections']:
                sub['steps'] = [s for s in sub.get('steps', []) if s != result['description']]

    return result

def download_images(images, num):
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
