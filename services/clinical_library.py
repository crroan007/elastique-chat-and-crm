# Clinical Protocol Library (V2)
# Evidence Levels: A=Human Direct, B=Edema/Venous Proxy, C=Mechanistic

CLINICAL_PROTOCOLS = {
    "foundation": {
        "title": "Whole-Body Foundation Stack",
        "description": "Daily baseline for all users.",
        "items": [
            {
                "name": "Aerobic Movement",
                "instruction": "Rhythmic movement (brisk walk is easiest).",
                "dose": "150 min/week moderate (30 min x 5 days)",
                "evidence": "B/C",
                "urls": ["https://www.cdc.gov/physical-activity-basics/guidelines/adults.html"]
            },
            {
                "name": "Diaphragmatic Breathing",
                "instruction": "Slow inhale (belly expands), long exhale to support thoracic pump.",
                "dose": "5 min/day (or 2-3 min, 2x/day)",
                "evidence": "C",
                "urls": ["https://pmc.ncbi.nlm.nih.gov/articles/PMC11187277/"]
            },
            {
                "name": "Thoracic Duct Pump Check",
                "instruction": "Use your normal cardio session to change thoracic duct dynamics.",
                "dose": "10-30 min moderate bout",
                "evidence": "A",
                "urls": ["https://www.nature.com/articles/s41598-025-99416-8"]
            }
        ]
    },
    "neck": {
        "title": "Neck & Terminus Region",
        "keywords": ["neck", "head", "face", "migraine", "fog"],
        "items": [
            {
                "name": "Supraclavicular MLD",
                "instruction": "Very gentle, rhythmic skin traction in collarbone hollows.",
                "dose": "15 min/session",
                "evidence": "A",
                "urls": ["https://pubmed.ncbi.nlm.nih.gov/33339196/"]
            },
            {
                "name": "Drainage-Friendly Posture Reset",
                "instruction": "Chin tucks, slow rotations, upper trap stretch.",
                "dose": "2-3 min/day",
                "evidence": "C",
                "contraindication": "If dizzy/vertebral issues, keep gentle."
            }
        ]
    },
    "legs": {
        "title": "Legs & Feet (The Pooling Zone)",
        "keywords": ["legs", "feet", "ankles", "calves", "swelling", "edema", "heaviness"],
        "items": [
            {
                "name": "Structured Calf Pump",
                "instruction": "Standing heel raises + bent-knee heel raises.",
                "dose": "3 sets x 20-30 reps, 3-5 days/week",
                "evidence": "B",
                "urls": ["https://pubmed.ncbi.nlm.nih.gov/14718821/", "https://pmc.ncbi.nlm.nih.gov/articles/PMC7238730/"]
            },
            {
                "name": "Leg Elevation",
                "instruction": "Legs above heart with comfortable support.",
                "dose": "15-20 min, 1-2x/day as needed",
                "evidence": "B",
                "urls": ["https://www.dovepress.com/elevate-to-alleviate--evidence-based-vascular-nursing-study-peer-reviewed-fulltext-article-NRR"]
            },
            {
                "name": "Afternoon Walk",
                "instruction": "Treadmill or brisk walking to clear afternoon pooling.",
                "dose": "30-50 min",
                "evidence": "B",
                "urls": ["https://pmc.ncbi.nlm.nih.gov/articles/PMC4561105/"]
            }
        ]
    },
    "post_op": {
        "title": "Post-Op Safety Protocol",
        "keywords": ["surgery", "liposuction", "bbl", "tummy tuck", "post-op"],
        "items": [
            {
                "name": "Safety First MLD",
                "instruction": "Focus ONLY on Supraclavicular (Neck) clearance to open exit pathways without touching surgical sites.",
                "dose": "15 min/session, very gentle",
                "evidence": "A",
                "urls": ["https://pubmed.ncbi.nlm.nih.gov/33339196/"]
            },
            {
                "name": "Compression Adherence",
                "instruction": "Follow surgeon guidelines strictly.",
                "dose": "24/7 or as prescribed",
                "evidence": "Clinical Standard"
            }
        ]
    },
    "arms": {
        "title": "Arms & Axillary Basin",
        "keywords": ["arms", "hands", "fingers", "axilla"],
        "items": [
            {
                "name": "Upper Body Pump Circuit",
                "instruction": "Band rows (x12) + Wall slides (x10) + Overhead reach (x8) + Hand open/close (x30).",
                "dose": "2 rounds, 8-12 min total",
                "evidence": "C",
                "urls": ["https://journals.librarypublishing.arizona.edu/lymph/article/3541/galley/3584/download/"]
            }
        ]
    }
}

EVIDENCE_KEYS = {
    "A": "Level A Evidence (Human Direct Lymph Metrics)",
    "B": "Level B Evidence (Edema/Venous Outcomes)",
    "C": "Level C Evidence (Mechanistic/Physiological Plausibility)"
}
