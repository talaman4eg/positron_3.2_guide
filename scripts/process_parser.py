#!/usr/bin/env python3
"""Extract guide content from HTML using proper HTMLParser, download images, generate clean markdown."""
import re, os, sys, json, urllib.parse, subprocess
from html.parser import HTMLParser
from pathlib import Path

BASE = Path('/home/talaman/apps/positron_guide')
IMG_DIR = BASE / 'img'
HTML_DIR = BASE / 'md_raw'

GUIDES = [
    ('8', 'base-plate'),
    ('9', 'final-assembly'),
    ('10', 'folding'),
    ('heatset', 'heatset-insert-tool'),
]

BLOCK_TAGS = {'div', 'section', 'article', 'nav', 'header', 'footer', 'main', 'aside'}

class GuideParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = {'title': '', 'description': '', 'sections': []}
        self.tag_stack = []
        self.text_buffer = ''
        self.in_title = False
        self.title_done = False

        self.current_section = None
        self.current_sub = None
        self.pending_steps = []
        self.pending_images = []

        self.img_alt = ''
        self.img_srcset = ''
        self.in_img = False
        self.img_depth = 0

        self.p_text = ''
        self.p_depth = 0
        self.in_p = False

        self.h_text = ''
        self.h_tag = ''

        self.filter_words = {
            'image(s)', 'click to view', 'referenced by step',
            'back to top', 'precision motion', 'step images',
            'ldo motion', 'search', 'products', 'makers', 'guides',
            'news', 'resellers', 'events', 'contact us', 'about us',
            'contents', 'cookie', '© 2026'
        }

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get('class', '')

        if tag == 'title' and not self.title_done:
            self.in_title = True

        if tag == 'img':
            self.in_img = True
            self.img_alt = attrs_dict.get('alt', '')
            self.img_srcset = attrs_dict.get('srcSet', '')

        # Track h2 with text-3xl
        if tag == 'h2' and 'text-3xl' in cls:
            self.h_tag = 'h2'
            self.h_text = ''

        # Track h3 with text-2xl
        elif tag == 'h3' and 'text-2xl' in cls:
            self.h_tag = 'h3'
            self.h_text = ''

        self.tag_stack.append(tag)

    def handle_data(self, data):
        if self.in_title and not self.title_done:
            self.result['title'] = data.strip()

        if self.h_tag in ('h2', 'h3'):
            self.h_text += data

    def handle_endtag(self, tag):
        if tag == 'title' and self.in_title and not self.title_done:
            self.title_done = True
            self.in_title = False
            self.result['title'] = self.result['title'].split(' | ')[0].strip()

        if tag == 'img' and self.in_img:
            self.in_img = False
            self._process_image()

        if tag == self.h_tag and self.h_tag in ('h2', 'h3'):
            self._process_heading()
            self.h_tag = ''

        if tag in self.tag_stack:
            self.tag_stack.pop()

    def _process_image(self):
        urls = re.findall(r'url=([^&\s"]+)', self.img_srcset)
        if not urls:
            return
        url = urllib.parse.unquote(urls[0].replace('&amp;', '&'))
        if 'ldomotion/media' not in url:
            return
        fn = url.split('media/')[-1]
        self.pending_images.append({'alt': self.img_alt, 'url': url, 'fn': fn})

    def _process_heading(self):
        text = re.sub(r'\s+', ' ', self.h_text).strip()
        self.h_text = ''

        if not text:
            return

        if self.current_section:
            # Check if this is a "Contents" section - skip it
            if text == 'Contents':
                return
            # Skip navigation headings
            if any(w in text.lower() for w in self.filter_words):
                return

        if self.h_tag == 'h2' or (not self.current_section):
            # Flush previous
            self._flush_pending()

            self.current_section = {'title': text, 'subsections': []}
            self.result['sections'].append(self.current_section)
            self.current_sub = None

        elif self.h_tag == 'h3' and self.current_section:
            self._flush_pending()
            self.current_sub = {'title': text, 'steps': []}
            self.current_section['subsections'].append(self.current_sub)

    def _flush_pending(self):
        if self.current_sub and self.pending_steps:
            self.current_sub['steps'] = self.pending_steps[:]
            self.pending_steps = []
        if self.pending_images:
            if self.current_sub:
                self.current_sub.setdefault('images', []).extend(self.pending_images[:])
            elif self.current_section:
                self.current_section.setdefault('intro_images', []).extend(self.pending_images[:])
            self.pending_images = []

    def handle_comment(self, data):
        pass


def extract_text_nodes(html):
    """Extract structured data using a custom approach for single-line HTML."""
    result = {
        'title': '',
        'description': '',
        'sections': [],
    }

    # Title from <title> tag
    m = re.search(r'<title>([^<]+)</title>', html)
    if m:
        result['title'] = m.group(1).strip().split(' | ')[0].strip()

    # Parse using HTMLParser approach but with manual tracking
    parser = GuideParser()
    parser.feed(html)

    # Flush remaining
    parser._flush_pending()

    return parser.result


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

        data = extract_text_nodes(html)
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
