# Interface design notes

**Design read.** A professional work tool for Swiss fiduciaries, closer to a public-sector service than to
a marketing page: trust first, dense information, little motion. Dials: variance 3, motion 2, density 6.

## Choices

- **Rhythm borrowed from IBM Carbon**, not its brand:
  - spacing steps of 4, 8, 12, 16, 24, 32 and 48 px;
  - body text at 15 px with 0.16 px tracking;
  - square corners everywhere;
  - depth from 1 px hairlines, not shadows.
- **Type.** IBM Plex Sans for text and IBM Plex Mono for references and numbers. Both are served from
  local files, so nothing is fetched at runtime.
- **One accent.** Petrol (`#0f5c63` light, `#6fb8b8` dark) marks settled results and interactive elements.
  Amber is reserved for "to be reviewed" and red for failures. There are no gradients.
- **Light and dark** themes follow `prefers-color-scheme`.
- **Icons.** Phosphor regular, copied locally (MIT). There are no emojis.
- **Centre piece.** The ownership diagram is SVG generated on the server:
  - the target company sits at the bottom, holders sit above it, one row per level;
  - settled owners have a solid accent outline, owners under review a dashed amber outline;
  - fiduciary links are dashed;
  - every node and edge opens its source line in the side panel.
- **Source panel.** It sticks to the right on wide screens and moves below the content on narrow
  screens. It shows the file, page, line, the cited line highlighted and two lines of context.
- **Copy.**
  - German and French only.
  - No dashes, no mention of AI, no marketing words.
  - Status words are plain: "Durch die Regeln bestimmt" / "Zu prüfen" and "Déterminé par les règles" /
    "À vérifier".
- **States.**
  - Empty case list: a short instruction.
  - Running analysis: a skeleton and the current extraction step, polled every 2.5 s.
  - Failed analysis: the model status in plain language.
