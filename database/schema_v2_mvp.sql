
-- ==========================================
-- ELASTIQUE CRM SCHEMA V2.0 (MVP)
-- Adds: Marketing Hub, Commerce, and Unified Timeline
-- ==========================================

-- 1. E-COMMERCE LAYER (The "Shopify" Mirror)
-- Stores what they bought so we can trigger "Post-Purchase" Protocols
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
    external_order_id VARCHAR(100), -- Shopify ID
    total_amount DECIMAL(10,2),
    currency VARCHAR(10) DEFAULT 'USD',
    status VARCHAR(50), -- paid, fulfilled, refunded
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
    sku VARCHAR(100),
    product_name VARCHAR(255),
    quantity INTEGER,
    price DECIMAL(10,2)
);

CREATE TABLE product_views (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    sku VARCHAR(100),
    viewed_at TIMESTAMPTZ DEFAULT NOW(),
    session_id VARCHAR(100) -- Link to Chat Session
);

-- 2. MARKETING LAYER (The "Frappe" Engine)
-- Tracks where they came from and who to email
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255),
    utm_source VARCHAR(100),
    utm_medium VARCHAR(100),
    utm_campaign VARCHAR(100),
    status VARCHAR(50) DEFAULT 'active', -- active, paused
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- "Segments" are dynamic lists defined by JSON Logic
-- Example Criteria: {"and": [{"sku": "leggings"}, {"pain_level": {">": 5}}]}
CREATE TABLE segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100),
    description TEXT,
    criteria JSONB, 
    last_count INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Campaigns targeting Segments
CREATE TABLE campaign_targets (
    campaign_id UUID REFERENCES campaigns(id),
    segment_id UUID REFERENCES segments(id),
    PRIMARY KEY (campaign_id, segment_id)
);

-- 3. UNIFIED TIMELINE (The "Twenty" Feed)
-- Aggregates Chats, Orders, and Voice Calls into one stream
CREATE TABLE timeline_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
    event_type VARCHAR(50), -- 'chat_started', 'voice_call_inbound', 'voice_call_outbound', 'order_placed'
    summary TEXT,           -- "Called about Leg Pain"
    metadata JSONB,         -- {duration: 120, recording_url: '...', call_sid: '...'}
    occurred_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. TENANCY (Future Scale)
-- Pre-baking Multi-Tenancy for B2B2C pivots
-- ALTER TABLE contacts ADD COLUMN tenant_id UUID;
-- ALTER TABLE orders ADD COLUMN tenant_id UUID;
