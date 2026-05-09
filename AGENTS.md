# LDO Motion Guides - Extraction Instructions

## Source

### All Guide URLs
- `https://ldomotion.com/guides/1---positron-v32---extruder` → `1_positron_3.2_extruder.md`
- `https://ldomotion.com/guides/2---positron-v32---z-column` → `2_positron_v32_z-column.md`
- `https://ldomotion.com/guides/3---positron-v32---z-drive` → `3_positron_v32_z-drive.md`
- `https://ldomotion.com/guides/4---positron-v32---bed-v-holder` → `4_positron_v32_bed-v-holder.md`
- `https://ldomotion.com/guides/5---positron-v32---touch-panel` → `5_positron_v32_touch-panel.md`
- `https://ldomotion.com/guides/6---positron-v32---toolhead` → `6_positron_v32_toolhead.md`
- `https://ldomotion.com/guides/7---positron-v32---spool-holder` → `7_positron_v32_spool-holder.md`
- `https://ldomotion.com/guides/8---positron-v32---base-plate` → `8_positron_v32_base-plate.md`
- `https://ldomotion.com/guides/9---positron-v32---final-assembly` → `9_positron_v32_final-assembly.md`
- `https://ldomotion.com/guides/10---positron-v32---folding` → `10_positron_v32_folding.md`
- `https://ldomotion.com/guides/heatset-insert-tool-guide` → `heatset_insert_tool.md`

- **Base image CDN**: `https://s3.ldomotion.com/ldomotion/media/`
- **Framework**: Next.js (uses `/_next/image` proxy for resizing)

## Repository Structure

```
├── README.md                          # Index with links to all guides
├── AGENTS.md                          # This file
├── *.md                               # 11 guide markdown files
├── img/                               # All images organized by guide number
│   ├── {1,2,3,4,5,6,7,8,9,10}/       # Numbered guide image directories
│   └── heatset/                       # Heatset insert tool images
├── md_raw/                            # Source HTML files from ldomotion.com
│   └── {1,2,3,4,5,6,7,8,9,10,heatset}.html
├── scripts/                           # Python extraction and maintenance tools
│   ├── rewrite_tables.py              # Rewrite guides with 2-column image tables
│   └── add_navigation.py              # Add/update prev/next/index navigation
└── skills/                            # Workflow skill definitions
    ├── extract_guide.md               # Full guide extraction workflow
    ├── refresh_guide.md               # Refresh existing guide from source
    └── verify_links.md                # Verify all image and cross-references
```

## Page Structure (Source HTML)
- Main title in `<h1>`
- Sections marked with numbered `<h2>` headings (e.g., "1. Parts to Print")
- Subsections under each section as `<h3>` (e.g., "Printed Parts", "Install the Shaft...")
- Each subsection is wrapped in `<div class="flex flex-col xl:flex-row min-h-[400px]">`
- Left panel: step text in `<div class="product-description-text">` blocks
- Right panel: image cards with `Referenced by step N` labels for step mapping

## Image URLs
Each image has two variants served through Next.js CDN:
- **Preview (640w)**: `/_next/image?url=<encoded_s3_url>&w=640&q=75`
- **Large (828w)**: `/_next/image?url=<encoded_s3_url>&w=828&q=75`

Both resolve to the same raw S3 `.webp` file. The `w` parameter only controls CDN resize. Downloaded images are converted to `.png` for broader compatibility.

To download directly from S3, use the raw URL:
```
https://s3.ldomotion.com/ldomotion/media/<filename>.webp
```

## Markdown Output Format

### Navigation (top and bottom of each page)
```markdown
---
**Index:** [README](README.md) &nbsp;|&nbsp; **Previous:** [Prev Title](prev.md) &nbsp;|&nbsp; **Next:** [Next Title](next.md)
```

First page only shows Index + Next. Last page only shows Index + Previous.

### Image Tables (2-column, centered)
Images are placed after subsection step text in a consolidated 2-column table:
```markdown
### Subsection Title
- Step text here.
- Another step here.

| | |
|:-:|:-:|
| [![filename](img/N/filename.preview.png)](img/N/filename.png) | [![filename2](img/N/filename2.preview.png)](img/N/filename2.png) |
```

Preview images are clickable links to the large version. Images are mapped to steps using `Referenced by step N` from the source HTML.

### Original Page Link
Each guide includes a blockquote link to the original source:
```markdown
> Original: [LDO Motion Guide](https://ldomotion.com/guides/...)
```

## Caveats

### Spaces in filenames
Source images from S3 may contain spaces (e.g., `Extruder Main Body.webp`). When downloading, URL-encode spaces as `%20`. After download, rename all image files to lowercase with dashes instead of spaces:
- `Extruder Main Body.webp` → `extruder-main-body.png`
- `bowden coupler.webp` → `bowden-coupler.png`
- `top cover, left.webp` → `top-cover-left.png`
- Example download:
  ```bash
  curl -sL -o "$DIR/Extruder Main Body.webp" "https://s3.ldomotion.com/ldomotion/media/Extruder%20Main%20Body.webp"
  ```

### Next.js image proxy
The `src` attribute on `<img>` tags points to `/_next/image?url=...`, not the raw S3 URL. Extract the `url` query parameter and decode it to get the actual S3 path.

### Image naming
Filenames are not sequential or consistent. Some have suffixes like `-1`, `-2`, etc. Always extract the actual filename from the `srcSet` or `url` parameter, don't guess. All stored filenames are lowercase with dashes (no spaces, no special characters).

### Image-to-step mapping
Each image card in the source HTML contains a `Referenced by step N` label. This maps images to their corresponding step (1-indexed within the subsection). Use this mapping to place images after the correct step text.

## Extraction Steps
1. Fetch the page HTML, save to `md_raw/<number>.html`
2. Parse headings for section/subsection structure
3. Extract text content for steps/descriptions
4. Extract all `<img>` tags, decode the `url` query param from `/_next/image` proxy
5. Download each image from S3 (both raw large and preview via CDN)
6. Convert webp to png, normalize filenames (lowercase, dashes)
7. Build markdown with proper structure, image tables, and navigation
8. Verify all image references resolve to existing files

## Maintenance Commands
- **Rewrite all guides**: `python3 scripts/rewrite_tables.py`
- **Update navigation**: `python3 scripts/add_navigation.py`
- **Verify links**: `python3 -c "import re,os,glob; [print(f'  BROKEN: {os.path.basename(md)}: {ref}') for md in glob.glob('*.md') if 'README' not in md and 'AGENTS' not in md for ref in re.findall(r'\(img/[^)]+\)', open(md).read()) if not os.path.exists(ref)]"`
