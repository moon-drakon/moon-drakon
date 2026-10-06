# Embedded font

These files are subsets of [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono).
The scripts inline them into the SVGs as base64 `@font-face` rules.

| File | Weight | Characters | Used by |
|---|---|---|---|
| `mono-portrait.woff2` | 400 | the portrait character ramp | `profile/portrait.svg` |
| `mono-label.woff2` | 400 | basic Latin | labels in `profile/hero.svg` |
| `mono-number.woff2` | 700 | digits and comma | numbers in `profile/hero.svg` |

Why inline the font:

- The portrait grid assumes each character is 0.6 em wide. JetBrains Mono matches that.
  Without it, a viewer whose default monospace font is narrower sees a squeezed portrait.
- An SVG loaded through `<img>` cannot fetch an external font. A data URI is the only option.

JetBrains Mono is licensed under the SIL Open Font License 1.1. See `OFL.txt`.
