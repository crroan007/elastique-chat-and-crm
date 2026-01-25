# GoHighLevel Bot Setup - Quick Start (5 minutes)

## What You Now Have ✅

```
elastique_products.json       (26 KB)  → Full product database
ghl_knowledge_base.json       (26 KB)  → Ready-to-import FAQ entries
ghl_product_tiles.json        (66 KB)  → HTML product tiles for chat
```

**All 30 Elastique products parsed with:**
- Product images
- Pricing (sale + regular)
- Description
- Product URLs
- Colors & sizes available

---

## 3-Step GHL Setup

### Step 1: Import Knowledge Base (2 min)
**In GoHighLevel Dashboard:**
1. Go: **Automation > Chatbots > [Your Bot Name] > Knowledge Base**
2. Click: **"Add Source" > "FAQs"**
3. Open `ghl_knowledge_base.json` in a text editor
4. Copy all the JSON content
5. Paste into GHL FAQ import dialog
6. Click: **"Import"** or **"Save"**

**Result:** Your bot now knows about all 30 Elastique products with pricing, descriptions, and links.

---

### Step 2: Create Product Recommendation Flow (2 min)
**In your bot automation:**

1. **Trigger:** User asks about products
   - "What leggings do you have?"
   - "Show me compression wear"
   - "What's on sale?"

2. **Action:** Search Knowledge Base
   - "Search KB for: {user_message}"

3. **Response:** Use product tile template
   ```
   Here's a product we think you'll love:

   {INSERT_HTML_TILE_HERE}
   ```

4. **Get HTML tile:**
   - Open `ghl_product_tiles.json`
   - Find your product
   - Copy the `content` field (the HTML)
   - Paste into bot response

---

### Step 3: Test & Deploy (1 min)
1. **Test bot** with product questions:
   - "Tell me about L'Original Leggings"
   - "What's the best bra?"
   - "Show me your MicroPerle technology"

2. **Expected responses:**
   - Bot pulls from Knowledge Base
   - Shows product details
   - Displays product link

3. **Deploy:** Publish bot to your Elastique website

---

## File Reference

### elastique_products.json
**Use for:** Internal product database, CRM sync, analytics
```json
{
  "title": "L'Original Leggings",
  "product_url": "https://elastiqueathletics.com/products/loriginal-leggings",
  "image_url": "https://cdn.shopify.com/...",
  "price": "$235.00",
  "original_price": "$165.00",
  "description": "OEKO-TEX® certified compression...",
  "available_colors": ["black", "navy", "olive", "java"],
  "available_sizes": ["XS", "S", "M", "L", "XL"],
  "benefits": "MicroPerle, lymphatic drainage, circulation"
}
```

### ghl_knowledge_base.json
**Use for:** Direct import to GHL Knowledge Base
```json
{
  "question": "Tell me about L'Original Leggings",
  "answer": "L'Original Leggings\n\nMicroPerle, lymphatic drainage...\n\nPrice: $235.00\n...",
  "product_url": "https://elastiqueathletics.com/products/loriginal-leggings",
  "image_url": "https://cdn.shopify.com/...",
  "type": "product_recommendation"
}
```

### ghl_product_tiles.json
**Use for:** Chat responses, product display
```json
{
  "format": "html",
  "content": "<div class=\"ghl-product-tile\">\n  <img src=\"...\" alt=\"L'Original Leggings\">\n  <h3>L'Original Leggings</h3>\n  <p>MicroPerle, lymphatic drainage</p>\n  <span>$235.00</span>\n  <a href=\"...\">View Product</a>\n</div>",
  "product": { ... }
}
```

---

## Product Tile HTML Preview

The tiles render like this in chat:

```
┌─────────────────────────────────┐
│  [Product Image 280x280px]      │
│                                 │
│  L'Original Leggings            │
│  MicroPerle, lymphatic drainage │
│  $235.00                         │
│  Sizes: XS, S, M, L, XL         │
│  [View Product →]               │
└─────────────────────────────────┘
```

Similar to the example tile you showed—clean, mobile-friendly, clickable.

---

## Sample Bot Conversation

**User:** "What compression leggings do you have?"

**Bot:** *Searches Knowledge Base* → Returns:

```
Our L'Original Leggings are perfect for maximum lymphatic support!

[PRODUCT TILE DISPLAYS HERE WITH IMAGE, PRICE, LINK]

They're made with OEKO-TEX® certified compression fabric and our
patented MicroPerle® technology to promote lymphatic drainage and
improve circulation.

4.85 ★★★★★ (397 reviews)
Price: $235.00 (was $165.00)
Available: XS-XL in black, navy, olive, java

Ready to learn more? Click "View Product" above!
```

---

## Revenue Attribution (Per SOW)

To track the 5% revenue share, tag each product interaction:

**GHL Automation:**
1. When bot recommends product → Tag: `product_recommended_{product_name}`
2. When user clicks link → Tag: `product_link_clicked`
3. When customer purchases → Tag: `product_purchase_attribution`

**Attribution Window:** 30 days (per your SOW)

---

## Updating Products

When Elastique adds new products or updates pricing:

**Manual Update:**
```bash
# In command line:
cd "c:\Homebrew Apps\Elastique - GPT_chatbot"
python ghl_catalog_parser.py
# New JSON files generated automatically
```

**Re-import to GHL:**
1. Delete old KB entries
2. Import new `ghl_knowledge_base.json`
3. Update product tiles in bot responses

---

## Troubleshooting

**Q: Product tiles not rendering in chat?**
A: Check if your GHL plan supports HTML. If not, use text-only format:
```
🛍️ L'Original Leggings
Price: $235.00 | Sizes: XS-XL
→ View: https://elastiqueathletics.com/products/loriginal-leggings
```

**Q: Missing product images?**
A: Image URLs are from Shopify CDN (HTTPS). If they don't load:
- Check HTTPS URL access
- Use fallback text description

**Q: Sizes/colors not showing?**
A: The Shopify API extracts from product variants. If missing:
- Verify variants are set up in Shopify admin
- Manually add to `ghl_knowledge_base.json` answer field

**Q: Want to add custom product info?**
A: Edit `ghl_knowledge_base.json` directly:
- Add details to "answer" field
- Re-import to GHL
- Or manually update in GHL admin

---

## What's Next

1. ✅ Import `ghl_knowledge_base.json` to GHL Knowledge Base
2. ✅ Create "Product Inquiry" automation flow
3. ✅ Copy product tile HTML into bot responses
4. ✅ Test bot with product questions
5. ✅ Set up attribution tracking
6. ✅ Deploy to Elastique website
7. ✅ Monitor conversations & optimize recommendations

**Timeline:** Full setup can be done in 30 minutes.

---

## Need Help?

- **GHL Docs:** https://docs.gohighlevel.com/
- **Elastique Products:** https://www.elastiqueathletics.com/collections/all
- **Questions?** Check `GHL_SETUP_GUIDE.md` for detailed documentation

---

**Generated:** November 22, 2024
**Total Products:** 30
**Ready to deploy:** Yes ✓
