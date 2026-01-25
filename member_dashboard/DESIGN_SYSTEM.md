# Elastique Design System PRD
**Version**: 1.0  
**Last Updated**: 2026-01-23  
**Codename**: "Chamfered Depth"

---

## 1. Design Philosophy

### Core Principles
1. **Futuristic, Not Generic** – Avoid rounded corners (the "AI default"). Use chamfered/cut corners for a sci-fi HUD feel.
2. **Premium Depth** – Multi-layer shadows create floating, tactile elements.
3. **Light & Clinical** – Matches the lymphatic health brand (clean, medical, trustworthy).
4. **Sharp Hierarchy** – Clear section labels, distinct visual zones.

---

## 2. Color Palette

### Primary Colors
| Name | Hex | Usage |
|------|-----|-------|
| **Primary** | `#2C3E50` | Text, sidebar, dark elements |
| **Accent** | `#00B894` | CTAs, highlights, success states |
| **Accent Light** | `#55EFC4` | Gradients, hover states |

### Neutrals
| Name | Hex | Usage |
|------|-----|-------|
| **Background** | `#F8FAFB` | Page background |
| **Surface** | `#FFFFFF` | Cards, panels |
| **Surface Alt** | `#F0F4F5` / `#FAFBFC` | Table headers, alt rows |
| **Border** | `#E8EDEF` | Dividers, card borders |
| **Muted Text** | `#636E72` | Secondary text, labels |

### Semantic Colors
| Name | Hex | Usage |
|------|-----|-------|
| **Blue** | `#3498db` | Chat, info |
| **Purple** | `#9b59b6` | Voice, calls |
| **Amber** | `#f39c12` | Notes, warnings |
| **Red** | `#e74c3c` | Tickets, errors |
| **Green** | `#27ae60` | Deals, success |

---

## 3. Typography

### Font Stack
```css
--font-heading: 'Playfair Display', serif;
--font-body: 'Inter', sans-serif;
--font-mono: 'JetBrains Mono', monospace;
```

### Hierarchy
| Element | Font | Size | Weight |
|---------|------|------|--------|
| Page Title | Playfair Display | 24px | Bold |
| Section Label | Inter | 10px | Semibold, uppercase, tracking-wider |
| Card Title | Playfair Display | 20px | Bold |
| Body Text | Inter | 14px | Regular |
| Small/Caption | Inter | 11-12px | Regular |
| Data/Numbers | Mono | 14px | Medium |

---

## 4. Shape Language: Chamfered Corners

### The Signature Cut
```css
/* Standard bottom-right chamfer */
.panel-chamfered {
  clip-path: polygon(
    0 0, 100% 0,
    100% calc(100% - 16px),
    calc(100% - 16px) 100%,
    0 100%
  );
}

/* Small chamfer (avatars, icons) */
.chamfer-small {
  clip-path: polygon(0 0, 100% 0, 100% 75%, 75% 100%, 0 100%);
}
```

### Apply To
✅ Panels, Avatars, Buttons, Icons, Active nav items  
❌ NOT inputs or small badges

---

## 5. Elevation (Multi-Layer Shadows)
```css
.depth-2 {
  box-shadow: 
    0 2px 4px rgba(0,0,0,0.02),
    0 4px 8px rgba(0,0,0,0.03),
    0 8px 16px rgba(0,0,0,0.03),
    0 16px 32px rgba(0,0,0,0.02);
}
```

---

## 6. Iconography

**Library**: Lucide React  
**Stroke**: 1.5  
**Size**: 18px standard

| Context | Icon |
|---------|------|
| Contacts | `Users` |
| Segments | `PieChart` |
| Campaigns | `Send` |
| Voice | `Phone` |
| Commerce | `ShoppingBag` |
| Chat | `MessageSquare` |
| Notes | `FileText` |
| Deals | `DollarSign` |

---

## 7. Anti-Patterns

| ❌ Avoid | ✅ Use Instead |
|----------|----------------|
| `border-radius` | `clip-path` chamfer |
| Emoji icons | Lucide SVG icons |
| Single shadow | Multi-layer depth |
| Circle avatars | Chamfered squares |

---

*Codename "Chamfered Depth" – Premium, futuristic, clinical.*
