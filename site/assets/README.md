# Brand assets

The CDS and institutional logos are the official white SVG assets served by the
[Clinical Data Science website](https://www.clinicaldatascience.nl/), downloaded on 21 October 2026.
Their artwork and colours are unchanged.

- `cds.svg`: `/themes/custom/cds_maastro/logo-dia.svg`
- `maastro.svg`: `/themes/custom/cds_maastro/assets/images/logo-maastro.svg`
- `maastricht-university.svg`: `/themes/custom/cds_maastro/assets/images/logo-maastricht-university.svg`
- `maastricht-umc.svg`: `/themes/custom/cds_maastro/assets/images/logo-maastricht-umc.svg`

`pubpulse.svg` is the original pulse mark, retained as an unused source asset.

`cds-icon.svg` uses the unmodified white emblem path from `cds.svg` on a square
Maastricht University navy (`#001c3d`) background. The PNG exports include a 32px favicon, 152px/167px/180px Apple touch icons,
and 192px/512px Android icons declared in `site.webmanifest`. The mobile icons use
a full-bleed background so the platform can apply its own corner mask.

The header, footer and browser icons all use the CDS emblem. `../favicon.ico`
contains classic 32-bit bitmap entries at 16px, 32px and 48px for broad browser
compatibility. `cds-mask.svg` uses the same emblem in black on a transparent
background for Safari pinned tabs. Icon URLs are versioned to refresh caches.
