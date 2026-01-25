-- Elastique CRM Schema (SQLite Version)
-- Optimized for Local Development & "True CRM" Features

-- ==========================================
-- 1. CRM & IDENTITY LAYER
-- ==========================================

-- Contacts: The "Golden Record"
CREATE TABLE contacts (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    phone TEXT,
    first_name TEXT,
    last_name TEXT,
    avatar_url TEXT,
    
    -- Demographics
    age_range TEXT,
    gender TEXT,
    location_city TEXT,
    location_state TEXT,
    location_country TEXT,
    timezone TEXT,
    
    -- Engagement Metrics
    total_conversations INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    total_media_uploads INTEGER DEFAULT 0,
    engagement_score REAL DEFAULT 0.0,
    purchase_propensity REAL DEFAULT 0.0,
    churn_risk REAL DEFAULT 0.0,
    lifetime_value REAL DEFAULT 0.00,
    
    -- RFM Scoring
    rfm_recency INTEGER,   -- Days since last interaction
    rfm_frequency INTEGER, -- Monthly interactions
    rfm_monetary REAL,
    
    -- Lifecycle & Segmentation
    lifecycle_stage TEXT DEFAULT 'visitor', -- visitor, lead, customer, vip, churned
    acquisition_source TEXT,
    acquisition_campaign TEXT,
    segments TEXT,      -- JSON Array
    custom_tags TEXT,   -- JSON Array
    preferences TEXT,   -- JSON Object
    
    -- Behavioral Profile
    primary_concerns TEXT,        -- JSON Array
    body_parts_discussed TEXT,    -- JSON Array
    products_interested TEXT,     -- JSON Array
    products_purchased TEXT,      -- JSON Array
    
    -- Conversation Context
    last_conversation_summary TEXT,
    
    -- Tracking
    known_ips TEXT, -- JSON Array
    last_ip TEXT,
    utm_history TEXT, -- JSON Object
    
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Identity Resolution
CREATE TABLE contact_identities (
    id TEXT PRIMARY KEY,
    contact_id TEXT,
    identity_type TEXT NOT NULL, -- 'email', 'ip_address', 'cookie_id'
    identity_value TEXT NOT NULL,
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    confidence_score REAL DEFAULT 0.5,
    FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
    UNIQUE(identity_type, identity_value)
);

-- Notes (CRM Feature)
CREATE TABLE contact_notes (
    id TEXT PRIMARY KEY,
    contact_id TEXT,
    author_id TEXT, -- 'system' or Manager ID
    content TEXT,
    note_type TEXT DEFAULT 'general', -- general, call_log, email_log
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);

-- Support Tickets (CRM Feature)
CREATE TABLE support_tickets (
    id TEXT PRIMARY KEY,
    contact_id TEXT,
    subject TEXT,
    status TEXT DEFAULT 'open', -- open, closed, pending
    priority TEXT DEFAULT 'medium',
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);

-- Products & Deals (CRM Feature)
CREATE TABLE deals (
    id TEXT PRIMARY KEY,
    contact_id TEXT,
    stage TEXT DEFAULT 'new', -- new, protocol_sent, cart_abandoned, closed_won, closed_lost
    amount REAL DEFAULT 0.0,
    currency TEXT DEFAULT 'USD',
    products TEXT, -- JSON List of product objects
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);

-- Deal History (For Historical Reporting)
CREATE TABLE deal_history (
    id TEXT PRIMARY KEY,
    deal_id TEXT,
    previous_stage TEXT,
    new_stage TEXT,
    changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT DEFAULT 'system',
    FOREIGN KEY(deal_id) REFERENCES deals(id) ON DELETE CASCADE
);

-- Ticket History (For SLA Tracking)
CREATE TABLE ticket_history (
    id TEXT PRIMARY KEY,
    ticket_id TEXT,
    previous_status TEXT,
    new_status TEXT,
    changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT DEFAULT 'system',
    FOREIGN KEY(ticket_id) REFERENCES support_tickets(id) ON DELETE CASCADE
);

-- Daily Snapshots (For fast Trend Reporting)
CREATE TABLE daily_snapshots (
    date TEXT PRIMARY KEY, -- 'YYYY-MM-DD'
    total_contacts INTEGER,
    total_leads INTEGER,
    total_customers INTEGER,
    pipeline_value REAL,
    open_tickets INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 2. CONVERSATION & INTELLIGENCE LAYER
-- ==========================================

CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    contact_id TEXT,
    session_id TEXT,
    
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    duration_seconds INTEGER,
    
    message_count INTEGER DEFAULT 0,
    user_message_count INTEGER DEFAULT 0,
    bot_message_count INTEGER DEFAULT 0,
    
    resolution_status TEXT DEFAULT 'active',
    sentiment_score REAL,
    
    primary_intent TEXT,
    secondary_intents TEXT, -- JSON Array
    
    protocol_url TEXT,
    fork_decision TEXT,
    
    FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE SET NULL
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    sender TEXT NOT NULL,
    content TEXT,
    content_type TEXT DEFAULT 'text',
    
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0,
    
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- ==========================================
-- 3. ANALYTICS EVENTS (Telemetry)
-- ==========================================

CREATE TABLE product_events (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    contact_id TEXT,
    product_id TEXT,
    event_type TEXT, -- impression, click, add_to_cart
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE issue_mentions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    contact_id TEXT,
    issue_category TEXT,
    issue_type TEXT,
    message_context TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_contacts_email ON contacts(email);
CREATE INDEX idx_identities_value ON contact_identities(identity_value);

-- ==========================================
-- 4. CONVERSATION INTELLIGENCE (V3)
-- ==========================================

CREATE TABLE conversation_metrics (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    
    user_need TEXT,
    plan_provided TEXT,
    alignment_met BOOLEAN DEFAULT 0,
    
    products_discussed TEXT, -- JSON List
    
    appointment_scheduled BOOLEAN DEFAULT 0,
    appointment_date TEXT, -- ISO8601
    
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
