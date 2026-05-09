# Extract Guide

Full workflow for extracting a new guide from ldomotion.com.

## When to Use

- Adding a new guide that doesn't exist in the repository
- Rebuilding a guide from scratch when the existing file is corrupted

## Steps

1. Fetch the HTML:
   ```bash
   curl -sL -o "md_raw/<N>.html" "https://ldomotion.com/guides/<url-slug>"
   ```

2. Run the rewrite script to generate markdown:
   ```bash
   python3 scripts/rewrite_tables.py
   ```

3. Run the navigation script:
   ```bash
   python3 scripts/add_navigation.py
   ```

4. Verify all image references resolve:
   ```bash
   python3 -c "import re,os,glob; [print(f'  BROKEN: {os.path.basename(md)}: {ref}') for md in glob.glob('*.md') if 'README' not in md and 'AGENTS' not in md for ref in re.findall(r'\(img/[^)]+\)', open(md).read()) if not os.path.exists(ref)]"
   ```

5. Update README.md with the new guide link
6. Update AGENTS.md GUIDE_MAP in both scripts if adding a new guide number
7. Commit changes

## Notes

- The `rewrite_tables.py` script handles all HTML parsing, image-to-step mapping, and table generation
- The `add_navigation.py` script adds Index/Previous/Next links to all guides
- Image filenames must be lowercase with dashes (no spaces)
- Source HTML is minified single-line; use the `product-description-text` class and `Referenced by step N` labels for parsing
