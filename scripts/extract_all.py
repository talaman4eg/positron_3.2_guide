#!/usr/bin/env python3
"""Full extraction: parse HTML, download images, generate markdown."""
import re, os, sys, urllib.parse, subprocess
from html import unescape
from pathlib import Path

BASE = Path('/home/talaman/apps/positron_guide')
IMG_DIR = BASE / 'img'
HTML_DIR = Path('/home/talaman/.local/share/opencode/tool-output')

GUIDES = [
    ('tool_e05f2c84b001CPSnK7HSLHyDIP', '2', 'z-column'),
    ('tool_e05f2d28c001yExcSE08BdbNV1', '3', 'z-drive'),
    ('tool_e05f2dab60010OcHf1GheFmM1M', '4', 'bed-v-holder'),
    ('tool_e05f2e51f001OoHqEFd0KLdRIp', '5', 'touch-panel'),
    ('tool_e05f2ef8f001nelZ7Bkl9Xir6H', '6', 'toolhead'),
    ('tool_e05f2fa26001K1I2STX4dPZi6a', '7', 'spool-holder'),
    ('tool_e05f3053a001GREe8IhPEkdoCc', '8', 'base-plate'),
    ('tool_e05f30fa4001SGx3qnNxaVP4So', '9', 'final-assembly'),
    ('tool_e05f31a04001VemUpdbyesiw3x', '10', 'folding'),
]

def decode_url(e):
    return urllib.parse.unquote(e.replace('&amp;', '&'))

def extract_ordered(html):
    """Extract all structural elements in document order."""
    elements = []

    # h2 sections
    for m in re.finditer(r'<h2[^>]*class="[^"]*text-3xl[^"]*"[^>]*>(.*?)</h2>', html, re.DOTALL):
        t = unescape(re.sub(r'<[^>]+>', '', m.group(1)).strip())
        elements.append(('h2', re.sub(r'\s+', ' ', t), m.start()))

    # h3 subsections
    for m in re.finditer(r'<h3[^>]*class="[^"]*text-2xl[^"]*"[^>]*>(.*?)</h3>', html, re.DOTALL):
        t = unescape(re.sub(r'<[^>]+>', '', m.group(1)).strip())
        elements.append(('h3', re.sub(r'\s+', ' ', t), m.start()))

    # paragraphs (step text)
    for m in re.finditer(r'<p[^>]*>(.*?)</p>', html, re.DOTALL):
        t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        t = re.sub(r'\s+', ' ', t)
        elements.append(('p', t, m.start()))

    # images
    for m in re.finditer(r'<img[^>]*alt="([^"]*)"[^>]*srcSet="([^"]*)"', html):
        urls = re.findall(r'url=([^&\s"]+)', m.group(2))
        if urls:
            url = decode_url(urls[0])
            if 'ldomotion/media' in url:
                fn = url.split('media/')[-1]
                elements.append(('img', {'alt': m.group(1), 'url': url, 'fn': fn}, m.start()))

    elements.sort(key=lambda x: x[2])
    return elements

def is_step_text(text):
    """Check if a paragraph is a meaningful step description."""
    if len(text) < 30:
        return False
    skip = ['image', 'click to view', 'referenced by', 'back to top',
            'precision motion', 'step images', 'contents', 'cookie',
            'ldo motion', 'search', 'products', 'makers', 'guides',
            'news', 'resellers', 'events', 'contact us', 'about us']
    return not any(s in text.lower() for s in skip)

def is_intro_text(text):
    """Check if text is intro/description text."""
    return 'before you' in text.lower() or 'please make sure' in text.lower() or \
           'this guide' in text.lower()

def is_note_text(text):
    """Check if text is a note/warning."""
    return 'for all the m2.5' in text.lower() or 'please use our screwdriver' in text.lower()

def process_guide(html_file, num, slug):
    """Process a single guide HTML file."""
    with open(html_file) as f:
        html = f.read()

    # Title
    title = ''
    m = re.search(r'<title>([^|]+)\|', html)
    if m:
        title = m.group(1).strip()

    # Description
    description = ''
    paras = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
    for p in paras:
        t = re.sub(r'<[^>]+>', '', p).strip()
        if 'this guide' in t.lower() and ('build' in t.lower() or 'assemble' in t.lower() or 'instruction' in t.lower()):
            description = t
            break

    # Extract ordered elements
    elements = extract_ordered(html)

    # Build structure
    sections = []
    current_section = None
    current_sub = None

    # Track state
    pending_steps = []  # steps before first subsection (intro)
    pending_images = []

    for etype, etext, _ in elements:
        if etype == 'h2':
            current_section = {'title': etext, 'subsections': [], 'intro_steps': [], 'intro_images': []}
            sections.append(current_section)
            current_sub = None
            pending_steps = []
            pending_images = []
        elif etype == 'h3' and current_section:
            # Flush pending steps to intro
            current_section['intro_steps'] = pending_steps[:]
            current_section['intro_images'] = pending_images[:]
            current_sub = {'title': etext, 'steps': [], 'images': []}
            current_section['subsections'].append(current_sub)
            pending_steps = []
            pending_images = []
        elif etype == 'p' and is_step_text(etext):
            if is_intro_text(etext) and current_section and not current_sub:
                pending_steps.append(etext)
            elif is_note_text(etext):
                pending_steps.append(etext)
            elif not is_intro_text(etext) and not is_note_text(etext):
                pending_steps.append(etext)
        elif etype == 'img':
            pending_images.append(etext)

    # Flush last pending
    if current_section:
        if current_sub:
            current_sub['steps'] = pending_steps[:]
            current_sub['images'] = pending_images[:]
        else:
            current_section['intro_steps'] = pending_steps[:]
            current_section['intro_images'] = pending_images[:]

    # Collect all images for download
    all_images = []
    for sec in sections:
        for img in sec.get('intro_images', []):
            all_images.append(img)
        for sub in sec['subsections']:
            for img in sub.get('images', []):
                all_images.append(img)

    return {
        'title': title,
        'description': description,
        'sections': sections,
        'images': all_images,
    }

def download_images(images, num):
    """Download all images for a guide."""
    img_dir = IMG_DIR / num
    img_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    for img in images:
        fn = img['fn']
        dest = img_dir / fn
        if dest.exists():
            continue

        # Download large
        encoded = fn.replace(' ', '%20')
        url = f"https://s3.ldomotion.com/ldomotion/media/{encoded}.webp"
        try:
            subprocess.run(['curl', '-sL', '-o', str(dest), url],
                          check=True, timeout=30, capture_output=True)
            # Download preview
            preview_url = f"https://ldomotion.com/_next/image?url={urllib.parse.quote(img['url'], safe='')}&w=640&q=75"
            preview_dest = img_dir / fn.replace('.webp', '.preview.webp')
            subprocess.run(['curl', '-sL', '-o', str(preview_dest), preview_url],
                          check=True, timeout=30, capture_output=True)
            downloaded += 1
        except Exception as e:
            print(f"  ERROR: {fn}: {e}")

    return downloaded

def gen_markdown(data, num):
    """Generate markdown from extracted data."""
    md = f"# {data['title']}\n\n"
    if data['description']:
        md += f"{data['description']}\n\n"

    for sec in data['sections']:
        md += f"## {sec['title']}\n\n"

        # Intro steps (before subsections)
        for step in sec.get('intro_steps', []):
            md += f"- {step}\n"
        for img in sec.get('intro_images', []):
            fn = img['fn'].replace(' ', '%20')
            md += f"  - [Preview](img/{num}/{fn}.preview.webp) [Large](img/{num}/{fn}.webp)\n"
        if sec.get('intro_steps') or sec.get('intro_images'):
            md += "\n"

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
    for fname, num, slug in GUIDES:
        html_file = HTML_DIR / fname
        if not html_file.exists():
            print(f"SKIP {num}: file not found")
            continue

        print(f"Processing guide {num}: {slug}...")
        data = process_guide(html_file, num, slug)

        print(f"  Title: {data['title']}")
        print(f"  Sections: {len(data['sections'])}")
        print(f"  Total images: {len(data['images'])}")

        # Download images
        dl = download_images(data['images'], num)
        print(f"  Downloaded: {dl} images")

        # Generate markdown
        md = gen_markdown(data, num)
        md_file = BASE / f"{num}_positron_v32_{slug}.md"
        with open(md_file, 'w') as f:
            f.write(md)
        print(f"  Written: {md_file.name}")
        print()

if __name__ == '__main__':
    main()
