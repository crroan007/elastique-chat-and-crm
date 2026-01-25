
import sqlite3

def migrate_v2():
    print("--- MIGRATING TO ELASTIQUE CRM V2.0 (Marketing + Voice) ---")
    conn = sqlite3.connect('data/elastique.db')
    cursor = conn.cursor()
    
    # 1. Orders
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id UUID PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
        external_order_id VARCHAR(100),
        total_amount DECIMAL(10,2),
        currency VARCHAR(10) DEFAULT 'USD',
        status VARCHAR(50), 
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id UUID PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
        sku VARCHAR(100),
        product_name VARCHAR(255),
        quantity INTEGER,
        price DECIMAL(10,2)
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product_views (
        id UUID PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
        sku VARCHAR(100),
        viewed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        session_id VARCHAR(100)
    );
    """)

    # 2. Marketing (Campaigns & Segments)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campaigns (
        id UUID PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        name VARCHAR(255),
        utm_source VARCHAR(100),
        utm_medium VARCHAR(100),
        utm_campaign VARCHAR(100),
        status VARCHAR(50) DEFAULT 'active',
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS segments (
        id UUID PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        name VARCHAR(100),
        description TEXT,
        criteria JSONB, 
        last_count INTEGER DEFAULT 0,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Unified Timeline (With Voice Support)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS timeline_events (
        id UUID PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
        event_type VARCHAR(50), 
        summary TEXT,           
        metadata JSONB,         
        occurred_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()
    print("SUCCESS: Schema V2 Applied.")

if __name__ == "__main__":
    migrate_v2()
