#!/usr/bin/env python3
"""Extract guide content from LDO Motion HTML files and output structured JSON."""
import re, sys, json, urllib.parse
from html import unescape

def decode_url(encoded):
    """Decode Next.js URL parameter."""
    return urllib.parse.unquote(encoded.replace('&amp;', '&'))

def extract_all(html):
    result = {
        'title': '',
        'description': '',
        'sections': [],
        'images': []
    }

    # Extract title from <title> tag
    m = re.search(r'<title>([^<]+?)\s*\|', html)
    if m:
        result['title'] = m.group(1).strip()

    # Extract description from h1's sibling paragraph or from JSON data
    # The meta description is [object Object], so we need to find it elsewhere
    # Look for the first paragraph after h1 in the main content area

    # Extract all S3 image URLs
    images = set()
    for m in re.finditer(r'url=(https%3A%2F%2Fs3\.ldomotion\.com[^&\s"\\]+)', html):
        decoded = decode_url(m.group(1))
        images.add(decoded)
    result['images'] = sorted(images)

    # Extract sections from h2 tags with text-3xl class
    # Extract subsections from h3 tags with text-2xl class
    # Extract step text from the JSON data in script tags

    # The actual content is in the __next_f script blocks as serialized JSON
    # Let's extract section titles, subsection titles, and step text

    # Section titles: h2 with text-3xl
    sections = []
    current_section = None

    # Find all structural elements in order
    elements = []

    # h2 sections
    for m in re.finditer(r'<h2[^>]*class="[^"]*text-3xl[^"]*"[^>]*>(.*?)</h2>', html, re.DOTALL):
        text = unescape(re.sub(r'<[^>]+>', '', m.group(1)).strip())
        text = re.sub(r'\s+', ' ', text)
        elements.append(('h2', text, m.start()))

    # h3 subsections
    for m in re.finditer(r'<h3[^>]*class="[^"]*text-2xl[^"]*"[^>]*>(.*?)</h3>', html, re.DOTALL):
        text = unescape(re.sub(r'<[^>]+>', '', m.group(1)).strip())
        text = re.sub(r'\s+', ' ', text)
        elements.append(('h3', text, m.start()))

    # Sort by position
    elements.sort(key=lambda x: x[2])

    # Now extract step content from JSON data
    # The step text is embedded as "text":"..." in the script blocks
    # Let's find all meaningful text blocks
    step_texts = []
    for m in re.finditer(r'"text":"((?:[^"\\]|\\.)*)"', html):
        text = m.group(1).replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
        # Filter for meaningful step content
        if len(text) > 40 and not any(skip in text.lower() for skip in [
            'ldo motion', 'precision motion', 'back to top', 'search',
            'products', 'makers', 'guides', 'news', 'resellers',
            'events', 'contact us', 'about us', 'cookie'
        ]):
            step_texts.append(text)

    # Build section structure
    current_section = None
    current_subsection = None
    step_idx = 0

    for etype, etext, _ in elements:
        if etype == 'h2':
            current_section = {'title': etext, 'subsections': []}
            result['sections'].append(current_section)
            current_subsection = None
        elif etype == 'h3' and current_section is not None:
            current_subsection = {'title': etext, 'steps': []}
            current_section['subsections'].append(current_subsection)

    # Assign step texts to subsections
    # We need a smarter approach - match step texts to subsections by order
    # Flatten all subsections
    all_subsections = []
    for sec in result['sections']:
        for sub in sec['subsections']:
            all_subsections.append(sub)

    # Distribute step texts among subsections
    for i, sub in enumerate(all_subsections):
        # Each subsection typically has 1-4 steps
        # Use heuristics based on typical guide structure
        start = i * 3  # rough estimate
        end = min(start + 4, len(step_texts))
        sub['steps'] = step_texts[start:end] if start < len(step_texts) else []

    # Also extract images per subsection from the HTML order
    # Images appear after step text in the HTML
    # Let's extract image filenames in order
    image_order = []
    for m in re.finditer(r'alt="([^"]*)"[^>]*srcSet="([^"]*url=([^&\s"]+)[^"]*)"', html):
        alt = m.group(1)
        url_encoded = m.group(3)
        url = decode_url(url_encoded)
        image_order.append({'alt': alt, 'url': url})

    # Also try a different pattern for images
    if not image_order:
        for m in re.finditer(r'<img[^>]*alt="([^"]*)"[^>]*srcSet="([^"]*)"', html):
            alt = m.group(1)
            srcset = m.group(2)
            for url_m in re.finditer(r'url=([^&\s"]+)', srcset):
                url = decode_url(url_m.group(1))
                if 'ldomotion/media' in url:
                    image_order.append({'alt': alt, 'url': url})

    result['image_order'] = image_order
    result['step_texts'] = step_texts

    return result

def main():
    if len(sys.argv) < 2:
        print("Usage: extract.py <html_file>")
        sys.exit(1)

    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        html = f.read()

    data = extract_all(html)
    print(json.dumps(data, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
