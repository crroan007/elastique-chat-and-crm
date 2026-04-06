import os
from pathlib import Path
import re
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Image, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.units import inch
from xml.sax.saxutils import escape
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

# Import URL validation and image scraping
try:
    from services.url_validator import URLValidator, ProductImageScraper
except ImportError:
    from url_validator import URLValidator, ProductImageScraper

# ═══════════════════════════════════════════════════════════════════════════════
# BRAND COLORS — Official Elastique Athletics Palette (Brand Guidelines 2026)
# ═══════════════════════════════════════════════════════════════════════════════

class BrandColors:
    """Official Elastique Athletics palette — Brand Guidelines H1 2026."""
    # ── Official Brand Colors ──
    MIDNIGHT = colors.HexColor("#231B1E")         # Headlines, body text, nav (15-20%)
    BONE = colors.HexColor("#F2F1EA")             # Backgrounds, product cards (30-40%)
    PORCELAIN = colors.HexColor("#FFFFFF")        # Clean digital backgrounds (30-40%)
    VITALITY = colors.HexColor("#E4F684")         # CTAs, highlights, badges (10-15%)
    AURA = colors.HexColor("#9784F6")             # Secondary accents, wellness (10-15%)
    
    # ── Backwards-compatible aliases (used throughout generate_pdf) ──
    DEEP_NAVY = MIDNIGHT
    SLATE = colors.HexColor("#2A2125")            # Slightly lighter Midnight
    TEAL = MIDNIGHT                               # Section header bg
    TEAL_LIGHT = colors.HexColor("#3A3035")       # Subtle header variant
    TEAL_SOFT = BONE                              # Alt-row backgrounds
    GOLD = colors.HexColor("#2A2125")             # Weekly header bg (Midnight variant)
    GOLD_SOFT = BONE                              # Alt-row backgrounds
    
    # ── Neutrals ──
    WHITE = PORCELAIN
    OFF_WHITE = BONE
    GRAY_100 = BONE
    GRAY_300 = colors.HexColor("#D4D4D4")
    GRAY_500 = colors.HexColor("#737373")
    GRAY_700 = colors.HexColor("#404040")
    GRAY_900 = MIDNIGHT
    
    # ── Status (safety sections) ──
    SUCCESS = colors.HexColor("#059669")
    WARNING = colors.HexColor("#D97706")
    DANGER = colors.HexColor("#DC2626")
    DANGER_SOFT = colors.HexColor("#FFF8F0")      # Warm bone-tinted for disclaimer


# ═══════════════════════════════════════════════════════════════════════════════
# LYMPHATIC HEALTH PRIMER - Modular Research Sections (WITH FULL URLs)
# ═══════════════════════════════════════════════════════════════════════════════

TARGETED_READING = {
    "general": [
        {
            "summary": "Clinical overview of the lymphatic system and how it supports fluid balance and immune function",
            "url": "https://my.clevelandclinic.org/health/body/21199-lymphatic-system"
        },
        {
            "summary": "Hospital guidance on lymphedema symptoms and treatment options",
            "url": "https://stanfordhealthcare.org/medical-conditions/blood-heart-circulation/lymphedema.html"
        },
    ],
    "wheelchair": [
        {
            "summary": "Upper-extremity lymphedema resources with seated considerations",
            "url": "https://journals.librarypublishing.arizona.edu/lymph/"
        },
    ],
    "cardiac": [
        {
            "summary": "Safe activity guidance for adults with cardiac conditions",
            "url": "https://www.cdc.gov/physical-activity-basics/guidelines/adults.html"
        },
    ],
    "pregnancy": [
        {
            "summary": "Pregnancy-related swelling overview and self-care guidance",
            "url": "https://www.nhs.uk/pregnancy/related-conditions/common-symptoms/swollen-ankles-feet-and-fingers/"
        },
        {
            "summary": "Clinical overview of pregnancy edema and when to seek care",
            "url": "https://www.mayoclinic.org/healthy-lifestyle/pregnancy-week-by-week/expert-answers/swollen-ankles/faq-20057721"
        },
    ],
    "post_op": [
        {
            "summary": "Post-surgical lymphatic obstruction care commonly includes compression, movement, and skin care",
            "url": "https://medlineplus.gov/ency/article/001117.htm"
        },
    ],
    "arms": [
        {
            "summary": "Upper-extremity lymphedema research resources",
            "url": "https://journals.librarypublishing.arizona.edu/lymph/"
        },
    ],
    "legs": [
        {
            "summary": "Clinical overview of lower-extremity lymphedema and treatment options",
            "url": "https://stanfordhealthcare.org/medical-conditions/blood-heart-circulation/lymphedema.html"
        },
    ],
    "travel": [
        {
            "summary": "Compression and movement are core tools for travel-related swelling",
            "url": "https://www.ncbi.nlm.nih.gov/books/NBK537239/"
        },
    ],
}

PRIMER_CELLULAR = [
    {
        "summary": "Inflammatory states can change lymphatic endothelial cell stress responses and metabolism",
        "url": "https://pubmed.ncbi.nlm.nih.gov/38710942/"
    },
    {
        "summary": "Lymphatic endothelial cells help regulate immune cell interactions",
        "url": "https://pubmed.ncbi.nlm.nih.gov/38754839/"
    },
    {
        "summary": "Macrophage–lymphatic interactions play a role in inflammatory signaling",
        "url": "https://pubmed.ncbi.nlm.nih.gov/39162663/"
    },
]

PRIMER_MECHANICAL = [
    {
        "summary": "Gentle arm exercise paired with deep breathing can support secondary arm lymphedema",
        "url": "https://journals.librarypublishing.arizona.edu/lymph/article/3541/galley/3584/download/"
    },
    {
        "summary": "Foam rolling influences recovery and tissue response after exercise",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7319325/"
    },
    {
        "summary": "Skin care is a core component of lymphedema management; gentle brushing can be used as light skin care",
        "url": "https://www.ncbi.nlm.nih.gov/books/NBK537239/"
    },
]

PRIMER_COMPRESSION = [
    {
        "summary": "Compression garments are a core component of lymphedema management",
        "url": "https://www.ncbi.nlm.nih.gov/books/NBK537239/"
    },
    {
        "summary": "L'Original Leggings provide a calibrated 13–8 mmHg gradient designed for daily supportive wear",
        "url": "https://www.elastiqueathletics.com/products/loriginal-leggings"
    },
    {
        "summary": "Lisse Leggings offer a gentle 18–21 mmHg graduated compression option for comfortable daily use",
        "url": "https://www.elastiqueathletics.com/products/lisse-leggings"
    },
]

PRIMER_CUTTING_EDGE = [
    {
        "summary": "NIH reports human evidence for brain waste-clearance pathways",
        "url": "https://www.nih.gov/news-events/nih-research-matters/brain-waste-clearance-system-shown-people-first-time"
    },
    {
        "summary": "Glymphatic system review explains CSF–ISF exchange and brain clearance pathways",
        "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4636982/"
    },
    {
        "summary": "Aging-focused review details how glymphatic function changes over time",
        "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11183173/"
    },
    {
        "summary": "Emerging research explores sensory stimulation and clearance dynamics of brain proteins",
        "url": "https://www.nia.nih.gov/news/nerve-stimulating-lights-and-sounds-may-trigger-removal-harmful-brain-proteins"
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# ELASTIQUE COMPRESSION PRODUCTS - Profile-Based Recommendations
# IMPORTANT: These are REAL verified products from elastiqueathletics.com
# ═══════════════════════════════════════════════════════════════════════════════

COMPRESSION_PRODUCTS = {
    "arms": [
        {"name": "Iconic 3/4 Sleeve MicroPerle Top", "url": "https://www.elastiqueathletics.com/products/iconic-top", "desc": "MicroPerle creates a massage-like sensory feel with movement for upper-body comfort"},
        {"name": "Iconic Lymphatic Long Sleeve Bodysuit", "url": "https://www.elastiqueathletics.com/products/iconic-microperle-long-sleeve-bodysuit-brief", "desc": "Full-body compression with arm, core, and pelvic support"},
    ],
    "legs": [
        {"name": "L'Original Leggings", "url": "https://www.elastiqueathletics.com/products/loriginal-leggings", "desc": "8\u201313 mmHg engineered compression with MicroPerle sensory feel\u2014many people feel lighter"},
        {"name": "L'Original Stirrup Leggings", "url": "https://www.elastiqueathletics.com/products/loriginal-stirrup-leggings", "desc": "Full-length with foot compression for travel comfort"},
        {"name": "Lisse Leggings", "url": "https://www.elastiqueathletics.com/products/lisse-leggings", "desc": "Graduated compression for a sleek, held feel\u2014also the sleep-friendly option"},
    ],
    "travel": [
        {"name": "L'Original Stirrup Leggings", "url": "https://www.elastiqueathletics.com/products/loriginal-stirrup-leggings", "desc": "Full foot compression designed for travel comfort"},
        {"name": "Lisse Leggings", "url": "https://www.elastiqueathletics.com/products/lisse-leggings", "desc": "Graduated compression for long travel days"},
    ],
    "wheelchair": [
        {"name": "Iconic 3/4 Sleeve MicroPerle Top", "url": "https://www.elastiqueathletics.com/products/iconic-top", "desc": "Upper body MicroPerle sensory support for seated comfort"},
        {"name": "Iconic Lymphatic Long Sleeve Bodysuit", "url": "https://www.elastiqueathletics.com/products/iconic-microperle-long-sleeve-bodysuit-brief", "desc": "Full torso compression for upper body comfort"},
        {"name": "L'Original Bra", "url": "https://www.elastiqueathletics.com/products/loriginal-bra", "desc": "Upper body compression support with MicroPerle"},
    ],
    "pregnancy": [
        {"name": "Adorn Leggings", "url": "https://www.elastiqueathletics.com/products/adorn-leggings", "desc": "Comfortable compression with MicroPerle for everyday wear"},
        {"name": "Lisse Leggings", "url": "https://www.elastiqueathletics.com/products/lisse-leggings", "desc": "Gentle graduated compression for comfort and support"},
    ],
    "post_op": [
        {"name": "L'Original Leggings", "url": "https://www.elastiqueathletics.com/products/loriginal-leggings", "desc": "Gentle compression for comfort (does not replace clinician-directed garments)"},
        {"name": "Lisse Leggings", "url": "https://www.elastiqueathletics.com/products/lisse-leggings", "desc": "Graduated compression for comfort support"},
    ],
    "general": [
        {"name": "L'Original Leggings", "url": "https://www.elastiqueathletics.com/products/loriginal-leggings", "desc": "Best seller\u20148\u201313 mmHg compression with MicroPerle sensory feel"},
        {"name": "Adorn Leggings", "url": "https://www.elastiqueathletics.com/products/adorn-leggings", "desc": "MicroPerle compression\u2014many people notice smoother-feeling skin"},
    ]
}

# ═══════════════════════════════════════════════════════════════════════════════
# LIFESTYLE RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════════════════════

LIFESTYLE_RECOMMENDATIONS = {
    "hydration": {"icon": "💧", "title": "Hydration", "text": "2.0-2.5 liters daily to support your sense of wellness"},
    "sleep": {"icon": "🌙", "title": "Sleep", "text": "7-8 hours nightly—quality sleep supports overall well-being"},
    "breathing": {"icon": "🫁", "title": "Breathing", "text": "5 minutes of diaphragmatic breathing daily encourages a feeling of lightness"},
    "movement": {"icon": "🚶", "title": "Movement", "text": "Gentle movement throughout the day supports fluid dynamics more than one intense session"},
}


class ProtocolGenerator:
    """
    Generates a premium, $100B-brand-quality Lymphatic Wellness Protocol PDF.
    Features luxurious styling, clickable links, and personalized product recommendations.
    """
    
    def __init__(self, output_dir=None):
        if output_dir is None:
            base_dir = Path(__file__).resolve().parents[1]
            output_dir = str(base_dir / "static" / "protocols")
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.C = BrandColors()  # Brand colors shorthand
        
    def _safe_filename(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            return "session"
        value = re.sub(r"[^A-Za-z0-9_-]+", "-", value)
        value = re.sub(r"-{2,}", "-", value).strip("-")
        return value or "session"

    def _safe_text(self, value: str) -> str:
        return escape(value or "")
    
    def _get_profile_tags(self, profile: dict) -> list:
        """Extract profile tags for recommendations."""
        tags = []
        mobility = str(profile.get("mobility", "")).lower()
        health = str(profile.get("health_status", "")).lower()
        issue = str(profile.get("issue_type", "")).lower()
        
        if "wheelchair" in mobility:
            tags.append("wheelchair")
        if any(x in health for x in ["cardiac", "heart", "lung"]):
            tags.append("cardiac")
        if "pregnant" in health:
            tags.append("pregnancy")
        if any(x in str(profile).lower() for x in ["surgery", "post-op", "liposuction"]):
            tags.append("post_op")
        if any(x in issue for x in ["arm", "hand", "axill"]):
            tags.append("arms")
        if any(x in issue for x in ["leg", "ankle", "foot", "knee", "thigh"]):
            tags.append("legs")
        if "travel" in str(profile).lower():
            tags.append("travel")
            
        return tags if tags else ["general"]
    
    def _get_product_recommendations(self, profile: dict) -> list:
        """Get compression products based on profile.
        
        Uses path-aware get_products_for_path() when goal_key is available,
        otherwise falls back to COMPRESSION_PRODUCTS tag-based lookup.
        """
        # --- PATH-AWARE: uses the same logic as the fork handler ---
        goal_key = profile.get("goal_key")
        if goal_key:
            from services.product_catalog import get_products_for_path, PRODUCT_CATALOG as CATALOG
            _REGION_TO_AREA = {
                "legs": "legs", "arms": "arms", "face": "face",
                "abdomen": "tummy", "general": "all", "neck": "face",
            }
            q2_area = _REGION_TO_AREA.get(profile.get("primary_region", "general"), "all")
            q3_context = profile.get("context_trigger", "")
            path_result = get_products_for_path(goal_key, q2_area, q3_context)
            
            products = []
            for key_name in ["primary", "complement"]:
                prod_key = path_result.get(key_name)
                if prod_key:
                    cat_entry = CATALOG.get(prod_key)
                    if cat_entry:
                        products.append({
                            "name": cat_entry["name"],
                            "url": cat_entry["url"],
                            "desc": cat_entry.get("mechanism", ""),
                        })
            if products:
                return products
        
        # --- FALLBACK: original tag-based system ---
        tags = self._get_profile_tags(profile)
        products = []
        seen = set()
        
        for tag in tags:
            for product in COMPRESSION_PRODUCTS.get(tag, []):
                if product["name"] not in seen:
                    products.append(product)
                    seen.add(product["name"])
        
        if len(products) < 2:
            for product in COMPRESSION_PRODUCTS.get("general", []):
                if product["name"] not in seen:
                    products.append(product)
                    seen.add(product["name"])
        
        return products[:4]

    def generate_pdf(
        self, 
        conversation_id, 
        user_name, 
        root_cause, 
        daily_items, 
        weekly_items, 
        email=None,
        profile=None,
        citations=None
    ):
        """Generate a premium, $100B-brand-quality protocol PDF."""
        safe_id = self._safe_filename(conversation_id)
        filename = f"Elastique-Protocol-{safe_id}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        
        profile = profile or {}
        citations = citations or []
        C = self.C  # Shorthand
        
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=48,
            leftMargin=48,
            topMargin=36,
            bottomMargin=36
        )
        styles = getSampleStyleSheet()

        # ═══════════════════════════════════════════════════════════════════
        # PREMIUM STYLES
        # ═══════════════════════════════════════════════════════════════════
        
        # Hero Title - HV Fitzgerald fallback (Georgia)
        hero_style = ParagraphStyle(
            'Hero',
            parent=styles['Heading1'],
            fontSize=36,
            textColor=C.DEEP_NAVY,
            alignment=TA_CENTER,
            spaceAfter=0,
            fontName='Times-Bold',
            leading=40
        )
        
        # Tagline - HV Fitzgerald fallback (Georgia)
        tagline_style = ParagraphStyle(
            'Tagline',
            parent=styles['Normal'],
            fontSize=12,
            textColor=C.GRAY_500,
            alignment=TA_CENTER,
            spaceAfter=20,
            fontName='Times-Bold',
            leading=16
        )
        
        # Section Header - Bold & Modern
        section_style = ParagraphStyle(
            'Section',
            parent=styles['Heading2'],
            fontSize=13,
            textColor=C.WHITE,
            spaceBefore=16,
            spaceAfter=8,
            fontName='Helvetica-Bold',
            backColor=C.TEAL,
            borderPadding=(8, 12, 8, 12),
            leading=18
        )
        
        # Subsection
        subsection_style = ParagraphStyle(
            'Subsection',
            parent=styles['Normal'],
            fontSize=11,
            textColor=C.DEEP_NAVY,
            spaceBefore=10,
            spaceAfter=4,
            fontName='Times-Bold'
        )
        
        # Body text
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontSize=10,
            textColor=C.GRAY_700,
            leading=14,
            alignment=TA_LEFT
        )
        
        # Label - Small caps feel
        label_style = ParagraphStyle(
            'Label',
            parent=styles['Normal'],
            fontSize=8,
            textColor=C.GRAY_500,
            spaceAfter=2,
            fontName='Helvetica-Bold'
        )
        
        # Value - Bold data
        value_style = ParagraphStyle(
            'Value',
            parent=styles['Normal'],
            fontSize=11,
            textColor=C.DEEP_NAVY,
            spaceAfter=6,
            fontName='Helvetica-Bold'
        )
        
        # Bullet points
        bullet_style = ParagraphStyle(
            'Bullet',
            parent=body_style,
            fontSize=10,
            leftIndent=16,
            bulletIndent=8,
            spaceBefore=3,
            spaceAfter=3
        )
        
        # Links - Clickable style
        link_style = ParagraphStyle(
            'Link',
            parent=styles['Normal'],
            fontSize=9,
            textColor=C.TEAL,
            leftIndent=12,
            spaceBefore=4,
            spaceAfter=2
        )
        
        # Product style
        product_style = ParagraphStyle(
            'Product',
            parent=styles['Normal'],
            fontSize=10,
            textColor=C.DEEP_NAVY,
            leftIndent=12,
            spaceBefore=6,
            spaceAfter=2
        )

        product_desc_style = ParagraphStyle(
            'ProductDesc',
            parent=body_style,
            fontSize=9,
            textColor=C.GRAY_500,
            leading=12
        )
        
        # Citation
        cite_style = ParagraphStyle(
            'Citation',
            parent=styles['Normal'],
            fontSize=8,
            textColor=C.GRAY_500,
            leftIndent=12,
            spaceBefore=2
        )
        
        # Disclaimer
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=body_style,
            fontSize=8,
            textColor=C.GRAY_700,
            alignment=TA_LEFT,
            backColor=C.DANGER_SOFT,
            borderPadding=10,
            leading=12
        )
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=C.GRAY_500,
            alignment=TA_CENTER
        )

        def build_source_sentence(summary, url, style, link_color="#000000", bullet=False):
            summary_text = self._safe_text(summary or "").strip()
            if not summary_text:
                return None
            if summary_text[-1] not in ".!?":
                summary_text += "."
            safe_url = self._safe_text(url)
            prefix = "• " if bullet else ""
            # Black underlined links to match elastiqueathletics.com brand
            return Paragraph(
                f"{prefix}{summary_text} (<a href=\"{safe_url}\" color=\"#000000\"><u>Source</u></a>)",
                style
            )
        
        story = []
        
        # ═══════════════════════════════════════════════════════════════════
        # PAGE 1: HEADER & USER INFO
        # ═══════════════════════════════════════════════════════════════════
        
        # Premium header with accent line
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=3, color=C.TEAL, spaceAfter=8))
        story.append(Paragraph("ELASTIQUE", hero_style))
        story.append(Paragraph("Your Personalized Lymphatic Wellness Protocol", tagline_style))
        story.append(HRFlowable(width="100%", thickness=1, color=C.GRAY_300, spaceAfter=16))
        
        # ─── User Info Card ───
        date_str = datetime.now().strftime("%B %d, %Y")
        safe_name = self._safe_text(user_name)
        safe_email = self._safe_text(email) if email else "—"
        
        info_data = [
            [
                Paragraph("<b>PREPARED FOR</b>", label_style),
                Paragraph("<b>DATE</b>", label_style),
                Paragraph("<b>EMAIL</b>", label_style)
            ],
            [
                Paragraph(safe_name, value_style),
                Paragraph(date_str, value_style),
                Paragraph(safe_email, value_style)
            ]
        ]
        
        info_table = Table(info_data, colWidths=[180, 150, 180])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C.OFF_WHITE),
            ('BOX', (0, 0), (-1, -1), 1, C.GRAY_300),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 16))
        
        # ─── Profile Summary ───
        if profile:
            story.append(Paragraph("YOUR PROFILE", section_style))

            profile_items = []
            if profile.get("health_status"):
                profile_items.append(f"<b>Health Status:</b> {self._safe_text(profile['health_status'])}")
            if profile.get("exercise_tolerance"):
                profile_items.append(f"<b>Exercise Tolerance:</b> {self._safe_text(profile['exercise_tolerance'])}")
            if profile.get("pregnancy_trimester"):
                tri_display = {"t1": "1st Trimester", "t2": "2nd Trimester", "t3": "3rd Trimester"}.get(
                    profile["pregnancy_trimester"], profile["pregnancy_trimester"])
                profile_items.append(f"<b>Pregnancy:</b> {self._safe_text(tri_display)}")
            if profile.get("mobility"):
                mob = profile['mobility']
                if isinstance(mob, list):
                    mob = ", ".join(mob)
                if mob:
                    profile_items.append(f"<b>Considerations:</b> {self._safe_text(str(mob))}")
            if profile.get("primary_region"):
                profile_items.append(f"<b>Primary Focus:</b> {self._safe_text(profile['primary_region'])}")
            if profile.get("issue_type"):
                profile_items.append(f"<b>Primary Focus:</b> {self._safe_text(profile['issue_type'])}")

            for item in profile_items:
                story.append(Paragraph(f"\u2022 {item}", bullet_style))
            story.append(Spacer(1, 8))
        
        # ─── Analysis & Focus ───
        story.append(Paragraph("ANALYSIS & FOCUS", section_style))
        safe_root = self._safe_text(root_cause)
        story.append(Paragraph(
            f"Based on our consultation, your primary focus is: <b>{safe_root}</b>. "
            "This protocol combines movement, compression support, and lifestyle adjustments "
            "tailored specifically to your needs.",
            body_style
        ))
        story.append(Spacer(1, 8))
        
        # ─── Expectation Setting ───
        expect_style = ParagraphStyle(
            'Expect', parent=body_style, fontSize=9,
            textColor=C.GRAY_700, backColor=C.TEAL_SOFT,
            borderPadding=10, leading=13
        )
        story.append(Paragraph(
            "<b>What to expect:</b> Wellness benefits from compression and movement are gradual. "
            "Most people notice a difference in comfort within 1–2 weeks of consistent use. "
            "This protocol is a starting point—listen to your body, adjust intensity as needed, "
            "and consult a healthcare provider if you have any concerns.",
            expect_style
        ))
        story.append(Spacer(1, 12))

        # ═══════════════════════════════════════════════════════════════════
        # HOW ELASTIQUE WORKS — Technology Explainer (Cert Module 6)
        # ═══════════════════════════════════════════════════════════════════

        tech_section = [
            Paragraph("HOW ELASTIQUE WORKS", section_style),
            Paragraph(
                "Elastique is engineered, third-party tested compression designed around fluid "
                "dynamics, with a patented MicroPerle\u00ae system that creates a massage-like sensory "
                "feel with movement\u2014so many people feel lighter and less heavy.",
                body_style
            ),
            Spacer(1, 6),
            Paragraph("\u2022 <b>Compression Dose:</b> 8\u201313 mmHg (core pieces), third-party tested at Hohenstein per DIN SPEC 4868", bullet_style),
            Paragraph("\u2022 <b>MicroPerle\u00ae:</b> Patented bonded hypoallergenic resin system\u2014sensory feel, not therapy", bullet_style),
            Paragraph("\u2022 <b>Materials:</b> Built with OEKO-TEX STANDARD 100\u2013certified components", bullet_style),
            Paragraph("\u2022 <b>Compliance:</b> Designed to be worn consistently\u2014the best compression is the one you actually wear", bullet_style),
            Spacer(1, 12),
        ]
        story.append(KeepTogether(tech_section))

        # ═══════════════════════════════════════════════════════════════════
        # LIFESTYLE FOUNDATIONS (Keep together)
        # ═══════════════════════════════════════════════════════════════════

        lifestyle_section = [
            Paragraph("LIFESTYLE FOUNDATIONS", section_style),
            Paragraph(
                "These wellness habits support your daily comfort and well-being:",
                body_style
            ),
            Spacer(1, 6)
        ]
        for key in ["hydration", "sleep", "breathing", "movement"]:
            rec = LIFESTYLE_RECOMMENDATIONS[key]
            lifestyle_section.append(Paragraph(
                f"{rec['icon']} <b>{rec['title']}:</b> {rec['text']}",
                bullet_style
            ))
        lifestyle_section.append(Spacer(1, 12))
        story.append(KeepTogether(lifestyle_section))
        
        # ═══════════════════════════════════════════════════════════════════
        # YOUR WEAR SCHEDULE — Context-adaptive (Cert Module 6)
        # ═══════════════════════════════════════════════════════════════════

        profile_tags = self._get_profile_tags(profile)
        
        # Determine context for wear schedule
        if "travel" in profile_tags:
            wear_title = "YOUR TRAVEL WEAR SCHEDULE"
            wear_rows = [
                ["Pre-departure", "Put on Elastique before leaving \u2014 compression works best when worn from the start"],
                ["In-transit", "Keep wearing during the entire journey; add ankle circles and calf pumps hourly"],
                ["Post-arrival", "Continue wearing for 1\u20132 hours after arrival; gentle walking helps"],
            ]
        elif any(t in profile_tags for t in ["wheelchair", "cardiac"]):
            wear_rows = [
                ["Morning", "Put on Elastique during your first movement of the day"],
                ["Throughout day", "Wear during seated periods \u2014 compression supports comfort when still"],
                ["Evening", "Remove before bed; Lisse is the sleep-friendly option if desired"],
            ]
            wear_title = "YOUR DAILY WEAR SCHEDULE"
        else:
            wear_title = "YOUR DAILY WEAR SCHEDULE"
            wear_rows = [
                ["Morning", "Put on Elastique before your first activity \u2014 start with at least 1 hour during movement"],
                ["Midday", "Continue wearing during long sitting, standing, or workouts"],
                ["Evening", "Remove before bed; if you want sleep-friendly compression, try Lisse"],
            ]
        
        wear_header_style = ParagraphStyle('WearTH', parent=body_style, textColor=C.WHITE, fontName='Helvetica-Bold')
        wear_data = [[
            Paragraph("<b>WHEN</b>", wear_header_style),
            Paragraph("<b>WHAT TO DO</b>", wear_header_style),
        ]]
        for when, what in wear_rows:
            wear_data.append([
                Paragraph(f"<b>{when}</b>", body_style),
                Paragraph(what, body_style),
            ])
        
        t_wear = Table(wear_data, colWidths=[120, 370])
        t_wear.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C.MIDNIGHT),
            ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.WHITE, C.BONE]),
            ('BOX', (0, 0), (-1, -1), 1, C.GRAY_300),
        ]))
        
        wear_section = [
            Paragraph(wear_title, section_style),
            Paragraph(
                "Results vary with fit, wear time, and movement. Listen to your body.",
                body_style
            ),
            Spacer(1, 6),
            t_wear,
            Spacer(1, 16),
        ]
        story.append(KeepTogether(wear_section))

        # ═══════════════════════════════════════════════════════════════════
        # DAILY PROTOCOL TABLE - Premium styling
        # ═══════════════════════════════════════════════════════════════════
        
        story.append(Paragraph("YOUR DAILY PROTOCOL", section_style))

        # Sub-text style for instruction/justification below action name
        action_sub_style = ParagraphStyle(
            'ActionSub', parent=body_style, fontSize=8,
            textColor=C.GRAY_500, leading=11, spaceBefore=2
        )

        daily_data = [[
            Paragraph("<b>ACTION</b>", ParagraphStyle('TH', parent=body_style, textColor=C.WHITE, fontName='Helvetica-Bold')),
            Paragraph("<b>FREQUENCY</b>", ParagraphStyle('TH', parent=body_style, textColor=C.WHITE, fontName='Helvetica-Bold'))
        ]]
        for item in daily_items:
            action = self._safe_text(item.get('action', '')).strip() or "\u2014"
            details = self._safe_text(item.get('details', '')).strip() or "\u2014"

            # Build rich action cell: name + instruction + adjustment note + source
            action_parts = [f"<b>{action}</b>"]
            instruction = item.get('instruction')
            if instruction:
                action_parts.append(f"<br/><font size='8' color='#737373'>{self._safe_text(instruction)}</font>")
            adj_note = item.get('adjustment_note')
            if adj_note:
                action_parts.append(f"<br/><font size='7' color='#231B1E'><i>{self._safe_text(adj_note)}</i></font>")
            urls = item.get('urls') or []
            if urls:
                safe_url = self._safe_text(urls[0])
                action_parts.append(f'<br/><font size="7" color="#231B1E"><a href="{safe_url}">Source</a></font>')

            daily_data.append([
                Paragraph("".join(action_parts), body_style),
                Paragraph(details, body_style)
            ])

        t_daily = Table(daily_data, colWidths=[320, 170])
        t_daily.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C.DEEP_NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.WHITE, C.TEAL_SOFT]),
            ('BOX', (0, 0), (-1, -1), 1, C.GRAY_300),
            ('LINEBELOW', (0, 0), (-1, 0), 2, C.TEAL),
        ]))
        story.append(t_daily)
        story.append(Spacer(1, 16))
        
        # ═══════════════════════════════════════════════════════════════════
        # WEEKLY GOALS TABLE
        # ═══════════════════════════════════════════════════════════════════
        
        if weekly_items:
            story.append(Paragraph("YOUR WEEKLY GOALS", section_style))
            weekly_data = [[
                Paragraph("<b>ACTIVITY</b>", ParagraphStyle('TH', parent=body_style, textColor=C.WHITE, fontName='Helvetica-Bold')),
                Paragraph("<b>TARGET</b>", ParagraphStyle('TH', parent=body_style, textColor=C.WHITE, fontName='Helvetica-Bold'))
            ]]
            for item in weekly_items:
                action = self._safe_text(item.get('action', '')).strip() or "—"
                details = self._safe_text(item.get('details', '')).strip() or "—"
                weekly_data.append([
                    Paragraph(action, body_style),
                    Paragraph(details, body_style)
                ])
                
            t_weekly = Table(weekly_data, colWidths=[320, 170])
            t_weekly.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), C.GOLD),
                ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.WHITE, C.GOLD_SOFT]),
                ('BOX', (0, 0), (-1, -1), 1, C.GRAY_300),
            ]))
            story.append(t_weekly)
            story.append(Spacer(1, 16))

        # ═══════════════════════════════════════════════════════════════════
        # CONTEXT PROTOCOL CARD — Travel / Desk / Active (Cert Module 3)
        # ═══════════════════════════════════════════════════════════════════

        if "travel" in profile_tags:
            context_title = "YOUR TRAVEL PROTOCOL"
            context_items = [
                ("\u2708\uFE0F Pre-Flight", "Hydrate well. Put on Elastique before heading to the airport."),
                ("\ud83d\udcba In-Flight", "Ankle circles and calf pumps every hour. Stay hydrated. Walk the aisle when possible."),
                ("\ud83c\udfef Post-Arrival", "Gentle walk within the first hour. Continue wearing Elastique for 1\u20132 hours."),
            ]
        elif any(t in profile_tags for t in ["wheelchair", "cardiac"]):
            context_title = "YOUR DAILY COMFORT PROTOCOL"
            context_items = [
                ("\u2600\uFE0F Morning", "Begin with diaphragmatic breathing. Put on Elastique during your first activity."),
                ("\ud83c\udf1e Midday", "Gentle upper-body movement or range-of-motion exercises. Stay hydrated."),
                ("\ud83c\udf19 Evening", "Remove Elastique before rest. Elevate legs if comfortable."),
            ]
        else:
            context_title = "YOUR DESK DAY PROTOCOL"
            context_items = [
                ("\u2600\uFE0F Morning", "Put on Elastique before your first activity. Start your day with movement."),
                ("\ud83c\udf1e Midday", "Stand, stretch, or walk for 5 minutes every hour. Calf pumps at your desk help."),
                ("\ud83c\udf19 Evening", "Gentle walk or stretching. Remove Elastique before bed."),
            ]

        context_section = [Paragraph(context_title, section_style)]
        for icon_time, instruction in context_items:
            context_section.append(Paragraph(
                f"<b>{self._safe_text(icon_time)}:</b> {self._safe_text(instruction)}", bullet_style
            ))
        context_section.append(Spacer(1, 16))
        story.append(KeepTogether(context_section))

        # ═══════════════════════════════════════════════════════════════════
        # PROGRESS SELF-CHECK (Cert-compliant felt outcomes)
        # ═══════════════════════════════════════════════════════════════════

        progress_style = ParagraphStyle(
            'Progress', parent=body_style, fontSize=9,
            textColor=C.GRAY_700, backColor=C.BONE,
            borderPadding=10, leading=13
        )
        # Build profile-aware self-check items
        region = (profile or {}).get("primary_region", "legs")
        mobility = (profile or {}).get("mobility", [])
        if isinstance(mobility, str):
            mobility = [m.strip() for m in mobility.split(",") if m.strip()]

        self_check_items = []
        if region == "arms" or "arms" in mobility or "hands" in mobility:
            self_check_items.append("\u25A2 Feeling of heaviness in arms or hands: <i>less / same / more</i>")
            self_check_items.append("\u25A2 Appearance of puffiness in hands: <i>less / same / more</i>")
        elif region == "neck":
            self_check_items.append("\u25A2 Feeling of tightness in neck and shoulders: <i>less / same / more</i>")
        else:
            self_check_items.append("\u25A2 End-of-day feeling of heaviness in legs: <i>less / same / more</i>")
            self_check_items.append("\u25A2 Appearance of puffiness after sitting: <i>less / same / more</i>")

        if "wheelchair" in mobility:
            self_check_items.append("\u25A2 Comfort during extended sitting: <i>better / same / worse</i>")
        else:
            self_check_items.append("\u25A2 Overall comfort during long sitting or standing: <i>better / same / worse</i>")

        self_check_items.append("\u25A2 General sense of lightness and wellness: <i>better / same / no change</i>")

        progress_section = [
            Paragraph("HOW TO KNOW IT\u2019S WORKING", section_style),
            Paragraph(
                "Track these felt outcomes over 1\u20132 weeks of consistent wear. "
                "Results vary with fit, wear time, and movement.",
                body_style
            ),
            Spacer(1, 6),
            Paragraph("<br/>".join(self_check_items), progress_style),
            Spacer(1, 16),
        ]
        story.append(KeepTogether(progress_section))

        # ═══════════════════════════════════════════════════════════════════
        # COMMON QUESTIONS — B→C Translation (Cert Module 5)
        # ═══════════════════════════════════════════════════════════════════

        myth_style = ParagraphStyle(
            'Myth', parent=body_style, fontSize=9,
            textColor=C.MIDNIGHT, leading=13
        )
        answer_style = ParagraphStyle(
            'MythAnswer', parent=body_style, fontSize=9,
            textColor=C.GRAY_700, leftIndent=12, leading=13,
            spaceBefore=2, spaceAfter=8
        )

        myths_section = [
            Paragraph("COMMON QUESTIONS", section_style),
            Paragraph("<b><i>\u201CIsn\u2019t this detox?\u201D</i></b>", myth_style),
            Paragraph(
                "No. Compression is mechanical pressure. It influences fluid dynamics\u2014where "
                "fluid tends to accumulate\u2014not chemical detoxification. Metabolic detoxification "
                "is performed by the liver and kidneys.",
                answer_style
            ),
            Paragraph("<b><i>\u201CMore compression = better?\u201D</i></b>", myth_style),
            Paragraph(
                "Not always. Excessive pressure can reduce tolerability and may impair superficial "
                "lymphatic flow. Consistency matters more than intensity.",
                answer_style
            ),
            Paragraph("<b><i>\u201CDo I need to wear it all day?\u201D</i></b>", myth_style),
            Paragraph(
                "Start with at least 1 hour during movement. Many people feel lighter right away. "
                "Results vary with fit, wear time, and movement.",
                answer_style
            ),
        ]

        # Add profile-specific FAQs
        health_status = (profile or {}).get("health_status", "")
        ctx_trigger = (profile or {}).get("context_trigger", "")
        preg_tri = (profile or {}).get("pregnancy_trimester")

        if preg_tri:
            myths_section.append(Paragraph("<b><i>\u201CIs compression safe during pregnancy?\u201D</i></b>", myth_style))
            myths_section.append(Paragraph(
                "Compression garments designed to support comfort are widely used during pregnancy. "
                "Always consult your healthcare provider before starting any new regimen, especially "
                "during the third trimester. Listen to your body and adjust as needed.",
                answer_style
            ))
        if "wheelchair" in mobility:
            myths_section.append(Paragraph("<b><i>\u201CHow do I use compression while seated all day?\u201D</i></b>", myth_style))
            myths_section.append(Paragraph(
                "Compression can support comfort during extended sitting. Pair with gentle breathing "
                "exercises and position changes when possible. Consistency in wear time supports "
                "the best sense of comfort throughout your day.",
                answer_style
            ))
        if ctx_trigger == "post_op" or health_status == "cardiac_pulm":
            myths_section.append(Paragraph("<b><i>\u201CWhen can I start after a procedure?\u201D</i></b>", myth_style))
            myths_section.append(Paragraph(
                "Always follow your healthcare provider\u2019s guidance on when to begin using compression "
                "or starting new movement routines. This protocol is a starting point\u2014your provider\u2019s "
                "instructions take priority.",
                answer_style
            ))

        myths_section.append(Spacer(1, 16))
        story.append(KeepTogether(myths_section))

        # ═══════════════════════════════════════════════════════════════════
        # SAFETY DISCLAIMER (Keep together to avoid page break cuts)
        # ═══════════════════════════════════════════════════════════════════

        disclaimer_text = (
            "<b>\u26A0\uFE0F IMPORTANT SAFETY INFORMATION</b><br/><br/>"
            "Elastique Athletics products are general wellness items intended to support comfort "
            "and cosmetic appearance. They are not medical devices and are not intended to diagnose, "
            "treat, cure, or prevent any disease or medical condition. Individual results may vary.<br/><br/>"
            "This protocol does not replace clinician-directed compression protocols or professional medical advice.<br/><br/>"
            "\u2022 <b>Consult your physician</b> before starting any new exercise or compression regimen<br/>"
            "\u2022 <b>Stop immediately</b> if you experience pain, shortness of breath, or unusual symptoms<br/>"
            "\u2022 <b>Seek medical attention</b> for sudden swelling, redness, warmth, or fever<br/><br/>"
            "<i>For clinical lymphedema treatment, consult a Certified Lymphedema Therapist (CLT).</i>"
        )
        
        # Compression Wearing Guide
        compression_guide = (
            "<b>\U0001F457 COMPRESSION WEARING GUIDE</b><br/><br/>"
            "\u2022 <b>Start with at least 1 hour during movement</b> \u2014 many people feel lighter right away; results vary with fit, wear time, and movement<br/>"
            "\u2022 <b>Best times:</b> During movement, travel, or prolonged sitting/standing<br/>"
            "\u2022 <b>Remove if:</b> You feel numbness, tingling, or increased discomfort<br/>"
            "\u2022 <b>Sleep:</b> Do not sleep in MicroPerle products; Lisse is the sleep-friendly option<br/>"
            "\u2022 <b>Care:</b> Hand wash cold, lay flat to dry \u2014 heat can degrade compression fibers<br/>"
            "\u2022 <b>Fit matters:</b> Compression should feel snug but never painful or restrictive"
        )
        
        compression_guide_style = ParagraphStyle(
            'CompressionGuide', parent=body_style, fontSize=8,
            textColor=C.GRAY_700, backColor=C.TEAL_SOFT,
            borderPadding=10, leading=12
        )
        
        # When to Seek Professional Help
        seek_help_text = (
            "<b>🩺 WHEN TO SEEK PROFESSIONAL HELP</b><br/><br/>"
            "Contact a healthcare provider promptly if you experience:<br/>"
            "• Sudden or unexplained swelling in one limb<br/>"
            "• Skin that is hot, red, or painful to the touch<br/>"
            "• Fever or chills alongside swelling<br/>"
            "• Swelling that does not improve with elevation and rest<br/>"
            "• Shortness of breath or chest pain<br/>"
            "• Open wounds or skin breakdown in swollen areas<br/><br/>"
            "<i>These may indicate a medical condition requiring prompt evaluation. "
            "This protocol does not replace professional medical advice.</i>"
        )
        
        seek_help_style = ParagraphStyle(
            'SeekHelp', parent=body_style, fontSize=8,
            textColor=C.GRAY_700, backColor=C.GOLD_SOFT,
            borderPadding=10, leading=12
        )
        
        safety_section = [
            HRFlowable(width="100%", thickness=1, color=C.GRAY_300, spaceBefore=8, spaceAfter=12),
            Paragraph(disclaimer_text, disclaimer_style),
            Spacer(1, 8),
            Paragraph(compression_guide, compression_guide_style),
            Spacer(1, 8),
            Paragraph(seek_help_text, seek_help_style),
            Spacer(1, 16)
        ]
        story.append(KeepTogether(safety_section))
        
        # ═══════════════════════════════════════════════════════════════════
        # RECOMMENDED PRODUCTS - Profile-Based with Live Images
        # ═══════════════════════════════════════════════════════════════════
        
        products = self._get_product_recommendations(profile)
        max_img_w = 0.9 * inch
        max_img_h = 0.9 * inch
        
        # Initialize URL validator and image scraper
        url_validator = URLValidator()
        image_scraper = ProductImageScraper()
        
        story.append(Paragraph("RECOMMENDED FOR YOU", section_style))
        story.append(Paragraph(
            "Based on your profile, we recommend these Elastique compression products:",
            body_style
        ))
        story.append(Spacer(1, 8))
        
        # Build product cards with images
        validated_products = []
        for p in products:
            # Validate URL first (catches soft 404s)
            validation = url_validator.validate_product_url(p['url'])
            if validation['valid']:
                # Get product image
                img_result = image_scraper.get_product_image(p['url'])
                p['image_path'] = img_result.get('local_path') if img_result['success'] else None
                p['validated'] = True
                validated_products.append(p)
            else:
                # Skip invalid products (404s, soft 404s)
                print(f"[URL Validator] Skipping invalid product: {p['name']} - {validation['reason']}")
        
        # If no valid products, use fallback text
        if not validated_products:
            fallback = build_source_sentence(
                "Explore the Elastique compression collection for additional supportive options",
                "https://www.elastiqueathletics.com/collections/best-sellers",
                body_style
            )
            if fallback:
                story.append(fallback)
        else:
            # Create product table with images
            product_rows = []
            
            for p in validated_products:
                # Build product cell content
                product_cell = []
                
                # Add product image if available
                if p.get('image_path') and os.path.exists(p['image_path']):
                    try:
                        img = Image(p['image_path'])
                        iw, ih = img.imageWidth, img.imageHeight
                        if iw and ih:
                            scale = min(max_img_w / iw, max_img_h / ih, 1.0)
                            img.drawWidth = iw * scale
                            img.drawHeight = ih * scale
                        img.hAlign = 'LEFT'
                        product_cell.append(img)
                    except Exception as e:
                        print(f"[PDF] Could not embed image: {e}")
                
                # Product name
                product_cell.append(Paragraph(
                    f"<b>{p['name']}</b>",
                    product_style
                ))

                # Description with source link
                desc_para = build_source_sentence(p.get('desc', ''), p['url'], product_desc_style)
                if desc_para:
                    product_cell.append(desc_para)
                
                product_rows.append(product_cell)
            
            # Create 2-column layout for products
            if len(product_rows) >= 2:
                # Two products per row
                table_data = []
                for i in range(0, len(product_rows), 2):
                    row = [product_rows[i]]
                    if i + 1 < len(product_rows):
                        row.append(product_rows[i + 1])
                    else:
                        row.append([])  # Empty cell
                    table_data.append(row)
                
                product_table = Table(table_data, colWidths=[245, 245])
                product_table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (0, 0), (-1, -1), C.OFF_WHITE),
                    ('BOX', (0, 0), (-1, -1), 1, C.GRAY_300),
                ]))
                story.append(product_table)
            else:
                # Single product - just add inline
                for cell in product_rows:
                    for elem in cell:
                        story.append(elem)
        
        story.append(Spacer(1, 8))
        more_products = build_source_sentence(
            "Explore the Elastique best-sellers collection for more compression options",
            "https://www.elastiqueathletics.com/collections/best-sellers",
            body_style
        )
        if more_products:
            story.append(more_products)
        
        # QR Code linking to main Elastique page
        qr_url = "https://www.elastiqueathletics.com"
        
        try:
            qr_code = QrCodeWidget(qr_url, barWidth=1.2*inch, barHeight=1.2*inch)
            qr_drawing = Drawing(1.2*inch, 1.2*inch)
            qr_drawing.add(qr_code)
            qr_drawing.hAlign = 'CENTER'
            
            qr_label = ParagraphStyle(
                'QRLabel', parent=footer_style, fontSize=8,
                textColor=C.GRAY_500, alignment=TA_CENTER, spaceAfter=4
            )
            story.append(Spacer(1, 8))
            story.append(Paragraph("Scan to shop your recommended product:", qr_label))
            story.append(qr_drawing)
        except Exception as e:
            print(f"[PDF] QR code generation failed: {e}")
        
        story.append(Spacer(1, 16))
        
        # ═══════════════════════════════════════════════════════════════════
        # LYMPHATIC HEALTH PRIMER
        # ═══════════════════════════════════════════════════════════════════

        profile_tags = self._get_profile_tags(profile)
        story.append(Paragraph("LYMPHATIC HEALTH PRIMER", section_style))
        story.append(Paragraph(
            "Targeted science highlights to deepen your understanding of lymphatic health:",
            body_style
        ))
        story.append(Spacer(1, 6))

        story.append(Paragraph("Targeted research based on your stated goals and needs", subsection_style))
        targeted_items = []
        seen_urls = set()
        # Include protocol-specific citations first
        for url in (citations or []):
            if url and url not in seen_urls:
                targeted_items.append({"summary": "Protocol-referenced source", "url": url})
                seen_urls.add(url)
        for item in TARGETED_READING.get("general", []):
            if item["url"] not in seen_urls:
                targeted_items.append(item)
                seen_urls.add(item["url"])
        for tag in profile_tags:
            for item in TARGETED_READING.get(tag, []):
                if item["url"] not in seen_urls:
                    targeted_items.append(item)
                    seen_urls.add(item["url"])
        if not targeted_items:
            targeted_items = TARGETED_READING.get("general", [])
        for item in targeted_items:
            para = build_source_sentence(item["summary"], item["url"], link_style, bullet=True)
            if para:
                story.append(para)

        story.append(Paragraph("Cellular & mitochondrial health", subsection_style))
        for item in PRIMER_CELLULAR:
            para = build_source_sentence(item["summary"], item["url"], link_style, bullet=True)
            if para:
                story.append(para)

        story.append(Paragraph("Mechanical support (movement + self-care)", subsection_style))
        for item in PRIMER_MECHANICAL:
            para = build_source_sentence(item["summary"], item["url"], link_style, bullet=True)
            if para:
                story.append(para)

        story.append(Paragraph("Compression dose \u2014 what Elastique measures", subsection_style))
        for item in PRIMER_COMPRESSION:
            para = build_source_sentence(item["summary"], item["url"], link_style, bullet=True)
            if para:
                story.append(para)

        story.append(Paragraph("Cutting-edge research (age, brain health, overall health)", subsection_style))
        for item in PRIMER_CUTTING_EDGE:
            para = build_source_sentence(item["summary"], item["url"], link_style, bullet=True)
            if para:
                story.append(para)

        story.append(Spacer(1, 16))
        
        # ═══════════════════════════════════════════════════════════════════
        # CONNECT WITH US — Community CTA
        # ═══════════════════════════════════════════════════════════════════

        cta_style = ParagraphStyle(
            'CTA', parent=body_style, fontSize=10,
            textColor=C.MIDNIGHT, alignment=TA_CENTER,
            backColor=C.BONE, borderPadding=16, leading=16
        )
        cta_section = [
            Spacer(1, 8),
            Paragraph("CONNECT WITH US", section_style),
            Spacer(1, 4),
            Paragraph(
                "Follow <b>@elastiqueathletics</b> for daily wellness insights, "
                "travel tips, and the science behind your garments.<br/><br/>"
                '<a href="https://www.elastiqueathletics.com" color="#231B1E"><u>elastiqueathletics.com</u></a>'
                " &nbsp;|&nbsp; "
                '<a href="https://www.instagram.com/elastiqueathletics" color="#231B1E"><u>@elastiqueathletics</u></a>',
                cta_style
            ),
            Spacer(1, 16),
        ]
        story.extend(cta_section)

        # ─── Premium Footer ───
        story.append(HRFlowable(width="100%", thickness=2, color=C.TEAL, spaceBefore=8, spaceAfter=8))
        story.append(Paragraph(
            "Generated by <b>Elastique</b> Lymphatic Wellness Platform",
            footer_style
        ))
        footer_link = build_source_sentence(
            "Explore more at elastiqueathletics.com",
            "https://elastiqueathletics.com",
            footer_style
        )
        if footer_link:
            story.append(footer_link)
        
        # Build
        doc.build(story)
        if not os.path.exists(filepath) or os.path.getsize(filepath) < 2000:
            raise RuntimeError(f"PDF generation failed or produced empty file: {filepath}")

        return filepath


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    gen = ProtocolGenerator()
    
    path = gen.generate_pdf(
        conversation_id="premium_wheelchair_demo",
        user_name="Marcus Wheeler",
        root_cause="Arms & Axillary Basin",
        daily_items=[
            {"action": "Upper Body Pump Circuit", "details": "2 rounds, 8-12 min total"},
            {"action": "Diaphragmatic Breathing", "details": "5 min (morning & evening)"},
            {"action": "Gentle Hand/Arm Self-Massage", "details": "10 min toward armpits"},
            {"action": "Compression Sleeve Wear", "details": "During waking hours as tolerated"},
        ],
        weekly_items=[
            {"action": "Zone 2 Upper Body Cardio", "details": "3x per week (20-30 min)"},
            {"action": "Skin Care Inspection", "details": "Check arms for changes"},
        ],
        email="marcus@test.com",
        profile={
            "health_status": "Mostly sedentary",
            "exercise_tolerance": "None (extremely limited)",
            "mobility": ["Wheelchair user", "Chronic pain"],
            "issue_type": "Arm and hand swelling"
        },
        citations=[
            "https://www.ncbi.nlm.nih.gov/books/NBK127642/",
            "https://journals.librarypublishing.arizona.edu/lymph/article/3541/",
            "https://www.cdc.gov/cancer-survivors/patients/lymphedema.html"
        ]
    )
    print(f"Generated: {path}")
