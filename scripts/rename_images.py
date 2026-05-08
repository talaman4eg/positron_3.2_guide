#!/usr/bin/env python3
"""
Rename all image files to use dashes instead of spaces/special chars,
update all markdown references, and convert previews to inline images.
"""
import os
import re
from pathlib import Path

BASE = Path("/home/talaman/apps/positron_guide")
IMG_DIR = BASE / "img"

def sanitize_filename(name):
    """Convert filename to lowercase, replace spaces/special chars with dashes."""
    # Decode URL encoding first
    name = name.replace("%20", " ")
    # Lowercase
    name = name.lower()
    # Replace spaces and commas with dash
    name = re.sub(r'[\s,]+', '-', name)
    # Collapse multiple dashes
    name = re.sub(r'-+', '-', name)
    # Strip leading/trailing dashes (but preserve the name)
    name = name.strip('-')
    return name

# Step 1: Build rename map for all image files
rename_map = {}  # old_path -> new_path

for img_file in IMG_DIR.rglob("*"):
    if not img_file.is_file():
        continue

    stem = img_file.stem  # filename without extension
    # Check if this is a preview file
    if stem.endswith('.preview'):
        # For preview files: strip .preview, sanitize, then add .preview back
        base_name = stem.replace('.preview', '')
        sanitized = sanitize_filename(base_name)
        new_stem = f"{sanitized}.preview"
    else:
        sanitized = sanitize_filename(stem)
        new_stem = sanitized

    new_name = f"{new_stem}{img_file.suffix}"
    old_name = img_file.name

    if old_name != new_name:
        rename_map[img_file] = img_file.with_name(new_name)

print(f"Files to rename: {len(rename_map)}")

# Step 2: Perform renames
for old_path, new_path in rename_map.items():
    # Ensure parent dir exists
    new_path.parent.mkdir(parents=True, exist_ok=True)
    os.rename(old_path, new_path)
    print(f"  {old_path.name} -> {new_path.name}")

# Step 3: Build string replacement map for markdown
# We need to replace all old filename references with new ones in .md files
# Collect all unique old->new name pairs (just the basename, for URL-encoded and literal forms)
str_replacements = {}

for old_path, new_path in rename_map.items():
    old_name = old_path.name
    new_name = new_path.name

    # The markdown might reference the file with %20 encoding
    url_encoded_old = old_name.replace(" ", "%20")
    str_replacements[url_encoded_old] = new_name
    str_replacements[old_name] = new_name

print(f"String replacements: {len(str_replacements)}")

# Step 4: Update all markdown files
md_files = list(BASE.glob("*.md"))
print(f"\nUpdating {len(md_files)} markdown files...")

for md_file in md_files:
    content = md_file.read_text()
    original = content

    # Replace all filename references
    for old_name, new_name in str_replacements.items():
        content = content.replace(old_name, new_name)

    # Convert preview links to inline images
    # Pattern: - [Preview](path) [Large](path)
    # To:       - ![Preview](path)
    #            [Large](path)
    content = re.sub(
        r'(-\s+)\[Preview\]\(([^)]+)\)\s*\[Large\]\(([^)]+)\)',
        r'\1![Preview](\2)\n  [Large](\3)',
        content
    )

    if content != original:
        md_file.write_text(content)
        print(f"  Updated: {md_file.name}")

print("\nDone!")
