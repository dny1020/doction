# Doction Design System

> This document is the visual source of truth for Doction.
> Every UI implementation must follow these guidelines unless a specific product requirement requires otherwise.
>
> **Do not invent a new visual language. Do not default to generic SaaS aesthetics.**
> Doction should feel like a carefully designed technical publishing tool: editorial, tactile, calm, precise and professional.

---

## 1. Design Direction

### Core concept

**Doction = technical software with an editorial soul.**

The visual identity combines:

* Editorial publishing
* Technical documentation
* Paper and physical materials
* Minimal modern software
* Subtle warm orange accents
* Dark green/charcoal ink tones
* Tactile, imperfect paper texture

The interface should feel **crafted rather than generated**.

### Keywords

Use these words to guide visual decisions:

* Editorial
* Tactile
* Paper
* Warm
* Technical
* Calm
* Precise
* Premium
* Minimal
* Human
* Quiet
* Structured

Avoid:

* Generic SaaS
* Corporate blue
* Purple AI gradients
* Excessive glassmorphism
* Excessive rounded cards
* Neon colors
* Huge gradients
* Excessive shadows
* Overly playful interfaces
* "AI-generated dashboard" aesthetics

---

# 2. Color System

Doction uses a warm paper foundation with dark ink and a restrained orange accent.

## Light Theme

### Background

```text
--background:        #F5F1E8
--background-subtle: #EFEADF
--surface:           #F9F7F1
--surface-elevated:  #FCFAF5
```

The primary background should resemble **warm natural paper**, not pure white.

Never use pure `#FFFFFF` as the primary application background.

### Ink

```text
--foreground:        #172522   /* 12.49:1 */
--foreground-muted:  #5F6864   /*  4.53:1 */
--foreground-subtle: #626763   /*  4.54:1 */
```

The primary text should resemble dark printing ink.

Avoid pure black `#000000`.

> **Amended 2026-09-08.** Every ratio in this document is measured against the **worst-case surface
> the token appears on**, not against `--background`. Ink sits on five surfaces here — background,
> subtle, surface, elevated and the §13 active-item ground `#E8E4DA` — and the darkest of them is
> what decides whether the value is readable. A token measured only against the page is a token
> that fails somewhere else in the interface.
>
> Two values changed as a result. `--foreground-subtle` was `#8B918C` (2.85:1 on the page, worse
> elsewhere). `--foreground-muted` was `#66706B`, which cleared 4.55:1 on the page but fell to
> **4.27:1** on the active-item ground. Both are now the lightest value on their own hue that holds
> 4.5:1 on all five.

### Borders

```text
--border:        #D8D2C5   /* 1.28:1 — decorative */
--border-subtle: #E5E0D6   /* 1.13:1 — decorative */
--border-strong: #858173   /* 3.07:1 — bounds a control */
```

Borders should be subtle and quiet.

> **Amended 2026-09-08.** A decorative line and a line that bounds a control are not the same job.
> `--border` at 1.34:1 may go unnoticed, and losing it costs nothing but tidiness. Anything a
> person clicks, types into or selects from needs at least 3:1 against the surface behind it, and
> §19 puts a border on every input — so a third token exists for that, and it is the one controls
> use. Decorative rules keep `--border`.

### Accent

Orange is Doction's signature accent. It is the **identity marker**: what the page points at.

```text
--accent:        #D97745   /* 2.48:1 worst case — decoration only */
--accent-hover:  #BE6035   /* 3.35:1 — decoration only */
--accent-soft:   #F3DDCC
--accent-muted:  #E9C4AB
--accent-ink:    #A34D21   /* 4.54:1 — orange that carries something */
```

Use orange sparingly.

Good uses:

* Small icons
* Active indicators
* Highlights
* Status indicators
* Small decorative elements

Do not turn the entire interface orange.

> **Amended 2026-09-08.** Orange on warm paper does not carry text: `#D97745` measures **2.48:1**
> at worst case and its hover **3.35:1**, against the 4.5:1 that anything readable needs. So orange
> marks rather than speaks.
>
> Two consequences for the list above. **"Important links" moves to the ink green**, which is where
> §10 already puts the controls a person acts on. **"Primary CTA accents" moves with it**: text on
> an orange fill measures 2.94:1, so an orange primary button is unreadable by the same arithmetic.
>
> **Orange itself splits by whether the mark carries information.**
>
> * `--accent` `#D97745` is **decoration**. A rule beside a heading, a flourish, a background wash,
>   an icon that repeats a label already written next to it. It clears no threshold and needs none,
>   because nothing is lost by not seeing it. This is the identity orange and it stays exactly as
>   specified.
> * `--accent-ink` `#A34D21` is **function**. An active-item indicator, a status dot, a selected
>   state, a small icon that is the only thing saying what it says. It clears 4.5:1, so it also
>   clears the 3:1 that a non-text UI component needs, and it is the form orange takes whenever it
>   has a job.
>
> The split is by consequence, not by size: ask what a reader loses if the mark is invisible. If
> the answer is nothing, use `--accent`. Otherwise use `--accent-ink`.
>
> This is not a retreat from the orange identity. It is what makes it survive contact with a
> reader: green ink for what you act on, orange for what the page is pointing at.

### Secondary identity color

Use a deep green/ink tone to distinguish Doction from typical SaaS products.

```text
--ink-green:       #173B35   /* 9.65:1 worst case */
--ink-green-hover: #0F302B   /* 11.19:1 */
--ink-green-soft:  #DDE7E2
```

This is the preferred color for primary buttons and important UI controls.

> **Amended 2026-09-08.** Read with the note above, this is the **interactive accent**: links, the
> active item, primary buttons, focus rings and selection. It is the hue a person clicks and the
> hue a person reads, and at 10.87:1 it is comfortable at every size.

---

# 3. Dark Theme

The dark theme should NOT simply invert the light theme.

It should feel like **dark paper / dark ink / warm studio lighting**.

Avoid the standard:

```text
#000000
#111111
#1E1E1E
```

Instead use warm charcoal tones.

```text
--background-dark:        #171614
--background-dark-subtle: #1D1B18
--surface-dark:           #211F1B
--surface-dark-elevated:  #28251F

--foreground-dark:        #E9E3D8   /* 11.96:1 worst case */
--foreground-dark-muted:  #938B7E   /*  4.54:1 */
--foreground-dark-subtle: #918B81   /*  4.52:1 */

--border-dark:            #39352F   /* 1.28:1 — decorative */
--border-dark-subtle:     #2E2B26   /* 1.13:1 — decorative */
--border-dark-strong:     #766D61   /* 3.00:1 — bounds a control */
```

> **Amended 2026-09-08.** Measured against the worst-case surface, as in §2 — here the *lightest*
> one, `--surface-dark-elevated`, since dark ink is light.
>
> `--foreground-dark-subtle` was `#777168` (3.74:1 on the page, 3.15:1 on elevated).
> `--foreground-dark-muted` was `#A7A096`, which looked comfortable at 6.99:1 on the page and is
> unchanged in character, only in value. `--border-dark-strong` is added because the dark theme
> must not drop a distinction the light one makes.

### Dark accent

The identity marker, as in the light theme.

```text
--accent-dark:       #E08A59   /* 5.78:1 worst case */
--accent-dark-hover: #ED9B6A
--accent-dark-soft:  #3A2920
```

Orange clears 4.5:1 against warm charcoal, so in the dark theme `--accent-dark` serves **both**
roles the light theme has to split: it is the decorative orange and the functional one. The split
in §2 exists because paper cannot hold orange, not because the roles differ by theme — so the
*rules* are identical in both themes, and only the number of tokens needed to obey them changes.

### Dark primary

The interactive accent, as in the light theme.

```text
--ink-green-dark:       #B9D0C7   /* 9.39:1 worst case */
--ink-green-dark-hover: #D0E0DA   /* 11.17:1 */
```

The dark theme should feel **warm, sophisticated and slightly orange**, but never brown or muddy.

---

# 4. Paper Texture

Paper texture is part of the Doction identity.

It should be **subtle enough to disappear when not noticed**.

The user should perceive:

> "This feels tactile."

not:

> "There is a paper texture behind the website."

### Texture characteristics

The texture should resemble:

* Natural off-white paper
* Very fine fibers
* Extremely subtle grain
* Slight tonal variation
* Occasional tiny imperfections

Avoid:

* Obvious noise
* Heavy grain
* Repeating patterns
* Parchment
* Vintage paper
* Yellow newspaper appearance
* Strong stains
* Fake aged-paper effects

### Implementation

Prefer CSS-generated texture or a tiny optimized texture asset.

Example conceptual implementation:

```css
background-color: #F5F1E8;
background-image:
  url("/textures/paper-noise.svg");
```

The texture opacity should generally remain between:

```text
0.025 - 0.06
```

It must never interfere with text readability.

### Paper hierarchy

Use different surfaces:

```text
Page
  ↓
Paper
  ↓
Elevated paper
  ↓
Floating element
```

Avoid excessive cards.

Paper should feel like a **material**, not a card UI gimmick.

---

# 5. Typography

Typography is a major part of the identity.

Use a combination of:

### Display / Editorial

Preferred:

```text
Fraunces
```

Fallback:

```text
Georgia, serif
```

Use it for:

* Major page titles
* Hero headings
* Editorial sections
* Documentation introductions
* Marketing headlines

Fraunces should be used selectively.

### Interface / UI

Preferred:

```text
Inter
```

Fallback:

```text
system-ui, sans-serif
```

Use for:

* Navigation
* Buttons
* Forms
* Metadata
* Tables
* Sidebars
* UI controls

### Code

Preferred:

```text
JetBrains Mono
```

Fallback:

```text
ui-monospace, SFMono-Regular, Menlo, monospace
```

Use for:

* Code
* API endpoints
* CLI commands
* Keyboard shortcuts
* Technical identifiers

---

# 6. Typography Scale

Use a restrained scale.

```text
Hero:
56px / 1.05

Page title:
42px / 1.1

Section title:
30px / 1.2

Subsection:
22px / 1.3

Body:
16px / 1.65

Lead:
18px / 1.55

Small:
14px / 1.5

Caption:
12px / 1.4

Code:
14px / 1.6
```

Desktop hero text may reach 64px, but do not make every heading enormous.

> **Amended 2026-09-08.** `Lead` is added because the application needs one step between body and
> subsection and had no legal value for it: a card title, an introductory paragraph, the largest
> thing that is still text rather than a heading. Without it those landed on 22px, which reads as a
> heading, or stayed at 16px, which erases the hierarchy. It is the one step this document did not
> name and the interface could not do without.

### Weight

Prefer:

```text
Regular
Medium
Semibold
```

Avoid excessive bold typography.

Editorial headings should generally feel **lighter and more elegant than a typical SaaS dashboard**.

---

# 7. Layout Philosophy

Doction should have generous whitespace.

The layout should feel intentional, not empty.

Use:

```text
8px
12px
16px
24px
32px
48px
64px
96px
128px
```

Avoid arbitrary spacing values unless necessary.

### Content width

Documentation reading width:

```text
680px - 760px
```

Marketing content:

```text
1100px - 1200px
```

Application:

```text
fluid
max-width only when appropriate
```

---

# 8. Border Radius

Doction should NOT look like a collection of pills.

Use restrained rounding.

```text
Small controls: 6px
Buttons:        7px
Cards:          10px
Panels:         12px
Large surfaces: 14px
```

Avoid:

```text
rounded-full
```

unless the element is genuinely circular or intentionally pill-shaped.

---

# 9. Shadows

Shadows should be almost invisible.

Prefer borders and tonal separation over strong shadows.

Example:

```css
box-shadow:
  0 1px 2px rgba(23, 37, 34, 0.04),
  0 4px 12px rgba(23, 37, 34, 0.04);
```

Never use large floating shadows for ordinary cards.

---

# 10. Buttons

Primary button:

```text
Background: #173B35
Text:       #F9F7F1
Radius:     7px
```

Hover:

```text
Background: #0F302B
```

Secondary button:

```text
Background: transparent
Border:     #D8D2C5
Text:       #172522
```

Accent button should use orange only when the action specifically deserves emphasis.

Buttons should feel like **printed labels / precise controls**, not giant SaaS pills.

---

# 11. Icons

Use a consistent outline icon system.

Preferred:

```text
Lucide
```

Icon characteristics:

* Thin/medium stroke
* Simple geometry
* 16–20px in UI
* 24px for feature illustrations
* Never mix multiple icon styles

Orange may be used for selected or contextual icons.

Do not use decorative icons everywhere.

---

# 12. Cards

Cards are allowed but should be used intentionally.

A Doction card should feel like a **sheet or panel**, not a floating Bootstrap component.

Preferred:

```text
background: var(--surface)
border: 1px solid var(--border-subtle)
border-radius: 10px
```

Avoid:

```text
huge shadow
huge radius
gradient background
multiple nested cards
```

### Important rule

**Do not put everything inside cards.**

If a section can exist naturally on the page without a container, prefer the open layout.

---

# 13. Navigation

Navigation should be quiet.

### Documentation

Left sidebar:

* Fixed or sticky
* Narrow
* Clear hierarchy
* Small typography
* Minimal active state

Active item:

```text
background: #E8E4DA
color:      #173B35
```

Use a thin accent indicator when useful.

### Application

The application can use a more conventional sidebar because productivity matters.

However:

* No oversized sidebar
* No excessive nested cards
* No visual clutter
* No unnecessary gradients

---

# 14. Documentation Design

The documentation site should feel like a **technical book printed on beautiful paper**.

Structure:

```text
┌──────────────────────────────────────────────────────────┐
│ Doction                         Search          Theme     │
├──────────────┬───────────────────────────────┬───────────┤
│              │                               │           │
│ Introduction │     Documentation             │ On this   │
│ Quick Start  │                               │ page      │
│ Concepts     │     Welcome to Doction        │           │
│ Guides       │                               │           │
│ API          │     Content...                │           │
│ SDKs         │                               │           │
│ Examples     │                               │           │
│              │                               │           │
└──────────────┴───────────────────────────────┴───────────┘
```

Documentation should prioritize:

1. Readability
2. Navigation
3. Search
4. Code examples
5. Information hierarchy

Do not sacrifice usability for the paper aesthetic.

---

# 15. Landing Page

The landing page should be more expressive than the application.

Use:

* Large editorial typography
* Paper texture
* Generous whitespace
* Product screenshots
* Technical diagrams
* Small orange details
* Subtle hand-drawn / imperfect elements where appropriate
* Strong visual hierarchy

The landing page should communicate:

> Doction is beautiful documentation software that you can own and self-host.

### Landing page personality

It should feel closer to:

```text
editorial publication
+
developer tool
+
premium software
```

than:

```text
generic startup landing page
```

Avoid the standard:

```text
gradient hero
+
three floating cards
+
purple glow
+
logos
+
giant rounded CTA
```

---

# 16. Application Design

The application is different.

The application must prioritize productivity.

The visual language remains Doction, but decorative elements are reduced.

### App principles

```text
Function first
Visual identity second
Decoration third
```

The app should feel:

* Fast
* Calm
* Dense enough for productivity
* Clear
* Professional
* Keyboard-friendly
* Consistent

Paper texture may exist, but at a lower intensity than the landing/docs.

Do not apply heavy texture to:

* Editors
* Tables
* Forms
* Dense data views
* Modals
* Code blocks

---

# 17. Editor

The editor is one of the most important Doction surfaces.

It should feel closer to **writing on a clean sheet of paper** than editing inside a generic SaaS card.

Prefer:

```text
open canvas
large readable typography
minimal chrome
subtle separators
comfortable line length
```

Avoid:

```text
card inside card
heavy borders
excessive toolbars
floating controls everywhere
```

---

# 18. Code Blocks

Code blocks should intentionally contrast with the paper environment.

Light mode:

```text
background: #E9E6DE
border:     #D8D2C5
```

Dark mode:

```text
background: #11110F
border:     #39352F
```

Use JetBrains Mono.

Code should feel technical and precise.

Orange may highlight important syntax or commands, but syntax highlighting must remain restrained.

---

# 19. Forms

Forms should be simple and quiet.

Input:

```text
background: transparent or surface
border:     1px solid var(--border)
radius:     7px
height:     40px - 44px
```

Focus:

```text
border: var(--accent)
box-shadow: 0 0 0 2px var(--accent-soft)
```

Do not use oversized inputs.

---

# 20. Tables

Tables should prioritize readability.

Use:

* Thin separators
* Comfortable row height
* Small typography
* Clear column alignment
* Minimal background decoration

Avoid:

* Every row inside a card
* Heavy borders
* Excessive rounded corners
* Gradient headers

---

# 21. Motion

Motion should be subtle.

Use approximately:

```text
Fast:    120ms
Normal:  180ms
Slow:    260ms
```

Prefer:

* opacity
* transform
* color
* background
* height

Avoid:

* excessive bouncing
* dramatic page transitions
* parallax everywhere
* exaggerated hover effects

Motion should communicate state, not entertain.

---

# 22. Responsive Design

Doction must remain usable from desktop to mobile.

Breakpoints:

```text
Mobile:  < 640px
Tablet:  640px - 1024px
Desktop: > 1024px
```

Documentation:

* Sidebar collapses on mobile
* Table of contents becomes contextual
* Search remains easy to access
* Reading width remains comfortable

Application:

* Sidebar becomes a drawer
* Dense layouts become stacked layouts
* Toolbars collapse intelligently
* Never simply shrink desktop UI until it breaks

---

# 23. Accessibility

Accessibility is part of the design system.

Requirements:

* Keyboard navigation
* Visible focus states
* Semantic HTML
* Accessible labels
* Sufficient contrast
* Reduced-motion support
* Never communicate state through color alone

Do not sacrifice accessibility for aesthetics.

---

# 24. Dark Mode Rules

Dark mode is not an afterthought.

It should preserve the same Doction identity:

```text
warm charcoal
+
cream typography
+
muted orange
+
deep green
```

Do not use:

```text
pure black
+
pure white
+
neon orange
```

The result should feel like **dark paper under warm light**.

---

# 25. Visual Anti-Patterns

Claude must actively avoid these patterns unless explicitly requested.

### Generic AI SaaS

```text
purple gradient
rounded cards
Inter everywhere
huge hero
glowing background
```

### Generic dashboard

```text
sidebar
+
four KPI cards
+
large chart
+
three tables
```

without a clear information architecture.

### Excessive glassmorphism

```text
backdrop-filter
blur
transparent cards
glows
```

Avoid by default.

### Excessive rounding

Do not make every UI element:

```text
rounded-full
```

### Excessive cards

Do not place every section inside a card.

### Decorative noise

Do not add:

* random blobs
* random gradients
* random illustrations
* random floating shapes
* meaningless animations

Every decorative element must have a reason.

---

# 26. Design Hierarchy

When making a design decision, use this priority:

```text
1. Usability
2. Information hierarchy
3. Readability
4. Consistency
5. Doction identity
6. Decoration
```

Never sacrifice usability for visual novelty.

---

# 27. Product Identity

The three Doction surfaces share the same design language but have different personalities.

```text
                 DOCTION
                    │
       ┌────────────┼────────────┐
       │            │            │
    Landing        Docs          App
       │            │            │
   Editorial     Technical    Functional
       │            │            │
    expressive     calm         focused
       │            │            │
       └────── shared identity ──┘
```

### Landing

Most expressive.

### Documentation

Editorial + technical.

### Application

Functional + technical.

The three should clearly feel like the same product.

---

# 28. Design Tokens

Use CSS variables or the project's existing design-token system.

Example:

```css
:root {
  --background: #F5F1E8;
  --background-subtle: #EFEADF;

  --surface: #F9F7F1;
  --surface-elevated: #FCFAF5;

  --foreground: #172522;
  --foreground-muted: #5F6864;
  --foreground-subtle: #626763;

  /* Two lines, two jobs. The first may go unnoticed; the second bounds a
     control and must not. */
  --border: #D8D2C5;
  --border-subtle: #E5E0D6;
  --border-strong: #858173;

  /* Orange splits by consequence, not by size. --accent decorates and may go
     unseen; --accent-ink carries something and clears 4.5:1. See §2. */
  --accent: #D97745;
  --accent-hover: #BE6035;
  --accent-soft: #F3DDCC;
  --accent-ink: #A34D21;

  /* The interactive accent. Links, primary buttons, the active item, focus,
     selection. */
  --ink-green: #173B35;
  --ink-green-hover: #0F302B;
  --ink-green-soft: #DDE7E2;

  --radius-sm: 6px;
  --radius-md: 7px;
  --radius-lg: 10px;
  --radius-xl: 14px;
}
```

Every value above is measured against the **worst-case surface it appears on** — the darkest in the
light theme, the lightest in the dark one — and the measurements live beside the tokens in §2 and
§3. Measuring against the page alone is how a value passes review and then fails on a hovered row.

A token whose value drifts from its stated ratio is a defect in this document before it is a defect
in the stylesheet.

---

# 29. Implementation Rules for Claude Code

When implementing or modifying Doction UI:

1. Read this file before making visual changes.
2. Preserve the existing design tokens whenever possible.
3. Reuse existing components before creating new ones.
4. Prefer composition over duplicated components.
5. Do not introduce another UI framework without explicit approval.
6. Do not introduce a new color palette.
7. Do not introduce another typography system.
8. Do not make arbitrary visual changes just to make a screen look "more modern".
9. Keep the paper texture subtle.
10. Keep orange restrained.
11. Keep the interface visually calm.
12. Test both light and dark themes.
13. Test responsive layouts.
14. Preserve accessibility.
15. When uncertain, prefer simplicity.

### Most important rule

**Do not make Doction look like a generic SaaS dashboard.**

The goal is not to maximize visual effects.

The goal is to create a recognizable Doction identity:

> **technical documentation software designed like a beautiful editorial tool.**

---

# 30. Reference Mental Model

When designing a new Doction screen, imagine:

```text
A beautifully printed technical book
        +
A modern developer tool
        +
A calm productivity application
        +
Subtle natural paper texture
        +
Dark green ink
        +
Warm orange annotation
```

That combination is the visual identity.

Doction should feel **quietly distinctive**, not loudly different.
