# Refresh Guide

Refresh an existing guide from the latest source HTML on ldomotion.com.

## When to Use

- The source guide on ldomotion.com has been updated
- You need to sync local markdown with upstream changes
- Images or steps have changed on the website

## Steps

1. Re-fetch the HTML:
   ```bash
   curl -sL -o "md_raw/<N>.html" "https://ldomotion.com/guides/<url-slug>"
   ```

2. Regenerate the markdown:
   ```bash
   python3 scripts/rewrite_tables.py
   ```

3. Update navigation:
   ```bash
   python3 scripts/add_navigation.py
   ```

4. Check for broken image references:
   ```bash
   python3 -c "import re,os,glob; [print(f'  BROKEN: {os.path.basename(md)}: {ref}') for md in glob.glob('*.md') if 'README' not in md and 'AGENTS' not in md for ref in re.findall(r'\(img/[^)]+\)', open(md).read()) if not os.path.exists(ref)]"
   ```

5. If new images were added, download them from S3 and convert webp to png
6. Commit changes with a descriptive message noting what changed

## Notes

- The rewrite script will overwrite the existing markdown file
- Existing images are preserved; only new images need downloading
- Navigation links are preserved by the add_navigation script
