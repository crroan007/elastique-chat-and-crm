# GoHighLevel Bot Training Setup Guide

## Overview
This guide shows how to integrate Elastique product catalog data into a GoHighLevel (GHL) chatbot using their Knowledge Base feature to serve product tiles.

---

## Files Generated

### 1. **elastique_products.json**
Structured product database with all metadata:
- Product title, SKU, URL
- Pricing (sale & original)
- Images, description
- Available sizes & colors
- Collection & style
- Key benefits

**Use case:** Bot training data, internal reference, CRM sync

### 2. **ghl_knowledge_base.json**
FAQ-formatted entries for GHL Knowledge Base:
- Question: "Tell me about [Product Name]"
- Answer: Product description, price, sizes, colors, link
- Type: product_recommendation

**Use case:** Direct import into GHL Knowledge Base > FAQs

### 3. **ghl_product_tiles.json**
Pre-formatted HTML product tiles ready for chat rendering:
- Product image
- Title & benefits
- Price (with discount badge if applicable)
- Available sizes
- "View Product" button/link

**Use case:** Bot response formatting, rich text responses in chat

---

## Setup Steps in GoHighLevel

### Step 1: Import Knowledge Base Entries
1. Log into **GoHighLevel Dashboard**
2. Navigate: **Automation > Chatbots > [Your Bot] > Knowledge Base**
3. Click **"Add Source"** and select **"FAQs"**
4. Paste content from `ghl_knowledge_base.json` entries
   - Question: FAQ question
   - Answer: Product details + link

### Step 2: Configure Bot Responses
1. Go to **Bot Settings > Response Templates**
2. Create a template for product recommendations:
```
When the user asks about products, recommend relevant items:

{PRODUCT_TILE_HTML}

Learn more: {PRODUCT_URL}
```

### Step 3: Create Training Conversations (Optional)
1. Use `ghl_knowledge_base.json` entries to create training examples
2. Example Q&A pairs:
   - Q: "What are your leggings like?"
   - A: "Our L'Original Leggings are made with MicroPerle® technology..." (from KB)

### Step 4: Configure Product Attribution Tags
1. In **Bot Settings > Attribution**
2. Add tags for:
   - `product_viewed_{product_name}`
   - `product_recommended_{category}`
   - `product_link_clicked`

3. Apply to conversions for revenue attribution (from SOW)

---

## Product Tile Implementation

### Option A: HTML Rich Text (Recommended)
GHL supports embedded HTML in rich text responses. Use the product tile from `ghl_product_tiles.json`:

```html
<div class="ghl-product-tile" style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px;">
    <img src="[IMAGE_URL]" alt="[PRODUCT]" style="width: 100%; height: 280px; object-fit: cover; border-radius: 6px;">
    <h3 style="margin: 12px 0 8px 0; font-size: 16px; font-weight: 600;">{PRODUCT_TITLE}</h3>
    <p style="margin: 8px 0; font-size: 13px; color: #666;">{BENEFITS}</p>
    <span style="font-size: 18px; font-weight: 700;">{PRICE}</span>
    <a href="{PRODUCT_URL}" target="_blank" style="display: inline-block; background: #2c3e50; color: white; padding: 10px 20px; border-radius: 4px; margin-top: 12px;">View Product</a>
</div>
```

### Option B: Card/Carousel (If GHL supports)
If your GHL plan supports card carousels:
1. Create cards with product data
2. Carousel layout for browsing multiple products
3. Click handlers for product links

### Option C: Text Summary with Link
Fallback if HTML not supported:
```
🏋️ {PRODUCT_TITLE}
${PRICE} (Regular: ${ORIGINAL_PRICE})
→ {BENEFITS}
Sizes: XS - XL
👉 View: {PRODUCT_URL}
```

---

## Bot Training Best Practices

### 1. Product Questions
Train the bot to recognize product inquiries:
- "What leggings do you have?"
- "Show me bras"
- "Tell me about compression"
- "What's your best seller?"

### 2. Benefit-Based Recommendations
Train based on user goals:
- **Lymphatic support** → L'Original, Iconic lines
- **Travel/comfort** → Lisse line
- **Fashion** → Fierce, Adorn collections
- **Swimwear** → Riviera Bodysuit

### 3. Size & Color Guidance
Knowledge Base entries include available sizes/colors:
- Help users find their size
- Suggest color options
- Link to size guide if available

### 4. Price Sensitivity
Use `ghl_knowledge_base.json` to train on:
- Sale vs. regular pricing
- Discount percentages
- Value propositions per price point

---

## Automation Flows

### Recommended Bot Flows:
1. **Product Inquiry** → Search KB → Return tile + link
2. **Size Question** → KB (includes sizes) → Offer size guide
3. **Price Question** → KB (includes pricing) → Link to checkout
4. **Recommendation Needed** → Ask user goals → Filter products → Show 2-3 tiles
5. **Product Click** → Tag visitor → Send SMS follow-up → Offer consultation

---

## Revenue Attribution (From SOW)

### Tracking Product Engagement:
1. Tag each product recommendation with `product_recommended_{name}`
2. When user clicks product link: tag `product_link_clicked_{name}`
3. On purchase: tag `product_purchased_{name}`
4. Track 30-day attribution window (per SOW)

### GHL Implementation:
- Use **Automation > Webhooks** to capture clicks
- Link webhook to **CRM > Attribution**
- Report on revenue influenced by bot recommendations (5% revenue share per SOW)

---

## Data Refresh

### Manual Refresh:
```bash
python ghl_catalog_parser.py
# Outputs updated JSON files
```

### Scheduled Refresh (Recommended):
1. Set up cron job (daily/weekly)
2. Auto-update `ghl_knowledge_base.json`
3. Re-import to GHL Knowledge Base
4. Keep product info current (sizes, prices, images)

---

## Support & Troubleshooting

**Product tiles not rendering?**
- Check HTML formatting in GHL rich text editor
- Test in preview mode first
- Fallback to text-only format if needed

**Missing product images?**
- Verify image URLs are accessible
- Use HTTPS only
- Test direct URL access in browser

**Sizes/colors missing?**
- Re-run `ghl_catalog_parser.py` to refresh
- Check Shopify product variants
- Add manually to `elastique_products.json` if needed

**Bot not recommending products?**
- Verify KB entries are published
- Check bot training/intent matching
- Test with exact phrases from KB entries

---

## Next Steps

1. ✅ Run `ghl_catalog_parser.py` to generate data files
2. ✅ Import `ghl_knowledge_base.json` to GHL Knowledge Base
3. ✅ Copy product tile HTML from `ghl_product_tiles.json`
4. ✅ Create bot responses using templates above
5. ✅ Set up attribution tracking
6. ✅ Test bot with sample conversations
7. ✅ Schedule regular data refresh

---

**Questions?** Contact Elastique Support or your GoHighLevel Account Manager.
