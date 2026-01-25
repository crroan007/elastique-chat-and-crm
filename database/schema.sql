-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- Enable Vector extension for Scientific Library
CREATE EXTENSION IF NOT EXISTS "vector";

-- ==========================================
-- 1. CRM & IDENTITY LAYER
-- ==========================================

-- Contacts: The "Golden Record"
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    avatar_url TEXT,
    
    -- Demographics
    age_range VARCHAR(20),
    gender VARCHAR(20),
    location_city VARCHAR(100),
    location_state VARCHAR(100),
    location_country VARCHAR(100),
    timezone VARCHAR(50),
    
    -- Engagement Metrics
    total_conversations INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    total_media_uploads INTEGER DEFAULT 0,
    engagement_score DECIMAL(5,2) DEFAULT 0.0,
    purchase_propensity DECIMAL(5,4) DEFAULT 0.0, -- 0.0 to 1.0
    churn_risk DECIMAL(5,4) DEFAULT 0.0,          -- 0.0 to 1.0
    lifetime_value DECIMAL(12,2) DEFAULT 0.00,
    
    -- RFM Scoring
    rfm_recency INTEGER,   -- Days since last interaction
    rfm_frequency INTEGER, -- Monthly interactions
    rfm_monetary DECIMAL(12,2),
    
    -- Lifecycle & Segmentation
    lifecycle_stage VARCHAR(50) DEFAULT 'visitor', -- visitor, lead, customer, vip, churned
    acquisition_source VARCHAR(100),
    acquisition_campaign VARCHAR(100),
    segments TEXT[],      -- Array of segment IDs or Names
    custom_tags TEXT[],   -- Manager applied tags
    preferences JSONB,    -- [NEW] Refinement answers: {compression: 'high', style: 'classic'}
    
    -- Behavioral Profile
    primary_concerns TEXT[],        -- e.g., ["swelling", "cellulite"]
    body_parts_discussed TEXT[],    -- e.g., ["legs", "ankles"]
    products_interested TEXT[],     -- e.g., ["original_leggings"]
    products_purchased TEXT[],
    
    -- Conversation Context
    last_conversation_summary TEXT, -- OVERWRITE: The 3-sentence summary of last chat
    
    -- Tracking
    known_ips TEXT[], -- History of IPs
    last_ip VARCHAR(50),
    utm_history JSONB, -- list of all UTM param objects seen
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Identity Resolution: Linking Cookies/IPs to Contacts
CREATE TABLE contact_identities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
    identity_type VARCHAR(50) NOT NULL, -- 'email', 'ip_address', 'cookie_id', 'fingerprint'
    identity_value VARCHAR(255) NOT NULL,
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    confidence_score DECIMAL(3,2) DEFAULT 0.5, -- 1.0 = Verified Email, 0.9 = Cookie, 0.5 = IP
    
    UNIQUE(identity_type, identity_value)
);

-- Segments (for Reporting/Targeting)
CREATE TABLE segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    segment_type VARCHAR(50) DEFAULT 'custom', -- 'auto', 'custom', 'smart'
    criteria JSONB, 
    contact_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================
-- 2. CONVERSATION & INTELLIGENCE LAYER
-- ==========================================

-- Conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    session_id VARCHAR(100), -- Browser session ID
    
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    
    message_count INTEGER DEFAULT 0,
    user_message_count INTEGER DEFAULT 0,
    bot_message_count INTEGER DEFAULT 0,
    
    resolution_status VARCHAR(50) DEFAULT 'active', -- active, resolved, abandoned, escalated
    sentiment_score DECIMAL(3,2), -- -1.0 to 1.0
    
    primary_intent VARCHAR(50),
    secondary_intents TEXT[],
    
    -- [NEW] Protocol & Path Tracking
    protocol_url TEXT,            -- Link to generated PDF
    fork_decision VARCHAR(50)     -- 'clothing' | 'consultation' | 'none'
);

-- Messages
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    sender VARCHAR(20) NOT NULL, -- 'user', 'bot', 'system'
    content TEXT,
    content_type VARCHAR(20) DEFAULT 'text', -- text, image, video, card
    
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    cost_usd DECIMAL(10,6) DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Media Uploads (Multimodal)
CREATE TABLE media_uploads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contact_id UUID REFERENCES contacts(id),
    conversation_id UUID REFERENCES conversations(id),
    
    file_type VARCHAR(20), -- photo, video
    file_url TEXT NOT NULL,
    storage_path TEXT,
    
    analysis_performed BOOLEAN DEFAULT FALSE,
    gemini_analysis JSONB, -- The structured findings from the vision model
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================
-- 3. SCIENTIFIC & KNOWLEDGE LAYER
-- ==========================================

-- Specific Citation Library (Vectorized)
CREATE TABLE scientific_library (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL, -- Friendly Name: "The 2010 Levick Study"
    url VARCHAR(500) NOT NULL,   -- Must be valid 200 OK
    
    key_findings TEXT,           -- Bullet points
    colloquial_phrasing TEXT,    -- "Interestingly, Dr. Levick found..."
    
    embedding vector(768),       -- Semantic Search Vector
    
    is_active BOOLEAN DEFAULT TRUE,
    last_verified_at TIMESTAMPTZ, -- Updated by Verification Script
    verification_status VARCHAR(20) DEFAULT 'verified' -- verified, broken, redirect
);

-- ==========================================
-- 4. ANALYTICS & REPORTING LAYER
-- ==========================================

-- Issue Tracking (Taxonomy)
CREATE TABLE issue_mentions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id),
    contact_id UUID REFERENCES contacts(id),
    
    issue_category VARCHAR(50), -- 'body_part', 'symptom', 'request'
    issue_type VARCHAR(100),    -- 'legs', 'swelling', 'sizing'
    
    message_context TEXT,       -- Snippet of text where it was mentioned
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Product Events
CREATE TABLE product_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id),
    contact_id UUID REFERENCES contacts(id),
    
    product_id VARCHAR(100),
    event_type VARCHAR(50), -- 'impression', 'click', 'add_to_cart', 'purchase'
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for basic performance
CREATE INDEX idx_contacts_email ON contacts(email);
CREATE INDEX idx_identities_value ON contact_identities(identity_value);
CREATE INDEX idx_conversations_contact ON conversations(contact_id);
