# Brand assets

The institutional logos are the official white SVG assets served by the
[Clinical Data Science website](https://www.clinicaldatascience.nl/), downloaded on 21 October 2026.
Their artwork and colours are unchanged. The CDS artwork now comes from the
supplied vector master `logo-cds.svg` (27 October 2026), preserved unchanged.

- `cds.svg`: white, renderer-compatible export of `logo-cds.svg`, used on the site
  and in both the Python and browser social-card generators. CSS fills are made
  explicit so PyMuPDF renders the white artwork correctly.
- `logo-cds-mask.svg`: full logo in black on transparency, suitable for an alpha mask.
- `maastro.svg`: `/themes/custom/cds_maastro/assets/images/logo-maastro.svg`
- `maastricht-university.svg`: `/themes/custom/cds_maastro/assets/images/logo-maastricht-university.svg`
- `maastricht-umc.svg`: `/themes/custom/cds_maastro/assets/images/logo-maastricht-umc.svg`
- `*-email.png`: high-resolution PNG exports of the four institutional logos,
  on navy backgrounds, for email clients that do not display SVG images.

`pubpulse.svg` is the original pulse mark, retained as an unused source asset.

`cds-icon.svg` uses the unmodified emblem path from `logo-cds.svg` in white on a square
Maastricht University navy (`#001c3d`) background. The PNG exports include a 32px favicon, 152px/167px/180px Apple touch icons,
and 192px/512px Android icons declared in `site.webmanifest`. The mobile icons use
a full-bleed background so the platform can apply its own corner mask.

The header, footer and browser icons all use the CDS emblem. `../favicon.ico`
contains classic 32-bit bitmap entries at 16px, 32px and 48px for broad browser
compatibility. `cds-mask.svg` uses the same emblem in black on a transparent
background for Safari pinned tabs and social-card watermarks. Both square variants
have an 8-unit inset around the emblem. Icon URLs are versioned to refresh caches.

Regenerate all derived SVG, PNG and ICO assets after updating the master:

```sh
python scripts/build_brand_assets.py
```

This uses the existing PyMuPDF and Pillow dependencies. Social cards remain
1200 × 627 px and render their logo and watermark from the SVG variants at the
required output size.
