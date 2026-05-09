# Verify Links

Verify all image references and cross-guide navigation links are valid.

## When to Use

- After regenerating guides to catch broken references
- Before committing changes
- Periodic integrity check

## Steps

1. Check all image references:
   ```bash
   python3 -c "import re,os,glob; [print(f'  BROKEN: {os.path.basename(md)}: {ref}') for md in glob.glob('*.md') if 'README' not in md and 'AGENTS' not in md for ref in re.findall(r'\(img/[^)]+\)', open(md).read()) if not os.path.exists(ref)]"
   ```

2. Check all cross-guide markdown links:
   ```bash
   python3 -c "import re,os,glob; md_files=set(os.path.basename(f) for f in glob.glob('*.md')); [print(f'  BROKEN: {os.path.basename(md)}: {ref}') for md in glob.glob('*.md') for ref in re.findall(r'\(([a-z0-9_\-]+\.md)\)', open(md).read()) if ref not in md_files]"
   ```

3. Check external URLs (optional):
   ```bash
   python3 -c "import re,urllib.request; [print(f'  {url}: {urllib.request.urlopen(url).status}') for url in set(re.findall(r'\]\((https://ldomotion\.com/[^)]+)\)', open('README.md').read()))]"
   ```

## Expected Output

- No output means all links are valid
- Any printed lines indicate broken references that need fixing

## Common Issues

- Missing `.preview.png` files (only large version exists)
- Filename mismatch after renaming (spaces vs dashes)
- Cross-guide links pointing to wrong filenames
