import sqlite3
import json
import os
import re
import hashlib
import secrets
import hmac
from datetime import datetime, timedelta

if os.environ.get("VERCEL"):
    import shutil
    tmp_db = "/tmp/store.db"
    orig_db = os.path.join(os.path.dirname(__file__), "store.db")
    if not os.path.exists(tmp_db) and os.path.exists(orig_db):
        try:
            shutil.copy2(orig_db, tmp_db)
        except Exception as e:
            pass
    DB_PATH = tmp_db if os.path.exists(tmp_db) else orig_db
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "store.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')

# ---------------------------------------------------------------------------
# CRYPTOGRAPHIC PASSWORD HASHING (PBKDF2-HMAC-SHA256, 200,000 Iterations)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Generate a cryptographically secure salted PBKDF2-HMAC-SHA256 hash."""
    salt = secrets.token_bytes(16)
    iterations = 200_000
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2:sha256:{iterations}${salt.hex()}${key.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    """Safely verify a password against a stored PBKDF2 hash using timing-safe comparison."""
    if not stored_hash:
        return False
    try:
        if stored_hash.startswith("pbkdf2:sha256:"):
            parts = stored_hash.split("$")
            if len(parts) == 3:
                algo_iter, salt_hex, key_hex = parts
                iterations = int(algo_iter.split(":")[-1])
                salt = bytes.fromhex(salt_hex)
                computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
                return hmac.compare_digest(computed.hex(), key_hex)
        # Fallback for legacy plain text migration
        return hmac.compare_digest(password, stored_hash)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

# ---------------------------------------------------------------------------
# DATABASE INITIALIZATION & SCHEMA DEFINITION
# ---------------------------------------------------------------------------

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY,
        store_name TEXT DEFAULT 'AURX WEAR',
        tagline TEXT DEFAULT 'Heavyweight Streetwear & Luxury Essentials',
        whatsapp_number TEXT DEFAULT '917851891611',
        email TEXT DEFAULT 'Dheerajgurjar7788@gmail.com',
        currency_symbol TEXT DEFAULT '₹',
        announcement_text TEXT DEFAULT '🔥 FREE SHIPPING ACROSS INDIA ON ALL ORDERS 🔥',
        admin_password TEXT,
        instagram_url TEXT DEFAULT 'https://instagram.com',
        banner_subtitle TEXT DEFAULT 'Premium Oversized Fits, Heavyweight Fabrics & Signature Graphics.'
    );
    """)

    # Categories table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        slug TEXT UNIQUE,
        display_order INTEGER DEFAULT 0
    );
    """)

    # Products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        price INTEGER NOT NULL,
        original_price INTEGER DEFAULT 0,
        badge TEXT DEFAULT '',
        sizes TEXT DEFAULT 'S,M,L,XL,XXL',
        description TEXT,
        fabric_details TEXT,
        images TEXT DEFAULT '[]',
        is_featured INTEGER DEFAULT 0,
        in_stock INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Orders table (Sales Tracking)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        customer_email TEXT DEFAULT '',
        shipping_address TEXT DEFAULT '',
        city TEXT DEFAULT '',
        state TEXT DEFAULT '',
        product_id INTEGER,
        product_title TEXT NOT NULL,
        product_image TEXT DEFAULT '',
        size TEXT NOT NULL,
        quantity INTEGER DEFAULT 1,
        unit_price INTEGER NOT NULL,
        total_price INTEGER NOT NULL,
        payment_method TEXT DEFAULT 'WhatsApp / UPI',
        status TEXT DEFAULT 'Confirmed',
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Returns table (Return & Refund Tracking)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS returns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        return_number TEXT UNIQUE NOT NULL,
        order_id INTEGER,
        order_number TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        product_title TEXT NOT NULL,
        size TEXT DEFAULT '',
        amount INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT DEFAULT 'Pending Review',
        admin_notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Site Visits table (Traffic & Visitor Analytics)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS site_visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visitor_id TEXT,
        ip_hash TEXT,
        page_url TEXT NOT NULL,
        page_title TEXT DEFAULT '',
        referrer TEXT DEFAULT '',
        device_type TEXT DEFAULT 'Desktop',
        browser TEXT DEFAULT 'Chrome',
        country TEXT DEFAULT 'India',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Admin Sessions table (Cryptographically secure persistent session tokens)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_sessions (
        session_token TEXT PRIMARY KEY,
        ip_address TEXT,
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP
    );
    """)

    # Login Attempts table (Brute-Force Attack Prevention & Lockout)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS login_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT NOT NULL,
        attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        success INTEGER DEFAULT 0
    );
    """)

    # Leads & Inquiries table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads_and_inquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT NOT NULL,
        product_title TEXT DEFAULT '',
        customer_name TEXT DEFAULT '',
        customer_contact TEXT DEFAULT '',
        message TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed default password hash for 'dheeraj@123'
    default_hash = hash_password("dheeraj@123")
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO settings (id, store_name, tagline, whatsapp_number, email, currency_symbol, announcement_text, admin_password, instagram_url, banner_subtitle)
        VALUES (1, 'AURX WEAR', 'Heavyweight Streetwear & Luxury Essentials', '917851891611', 'Dheerajgurjar7788@gmail.com', '₹', '🔥 FREE SHIPPING ACROSS INDIA ON ALL ORDERS 🔥', ?, 'https://instagram.com', 'Premium Oversized Fits, Heavyweight Fabrics & Signature Graphics.')
        """, (default_hash,))
    else:
        # Ensure password is set to hashed 'dheeraj@123'
        cursor.execute("UPDATE settings SET admin_password = ? WHERE id = 1", (default_hash,))

    # Seed categories if empty
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        initial_cats = [
            ("Oversized T-Shirts", "oversized-t-shirts", 1),
            ("Hoodies & Sweatshirts", "hoodies-sweatshirts", 2),
            ("Acid Wash & Vintage", "acid-wash-vintage", 3),
            ("Cargo & Parachute Pants", "cargo-pants", 4),
            ("Jackets & Outerwear", "jackets-outerwear", 5),
            ("Caps & Accessories", "accessories", 6),
        ]
        cursor.executemany("INSERT OR IGNORE INTO categories (name, slug, display_order) VALUES (?, ?, ?)", initial_cats)

    # Seed sample products if empty
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        sample_products = [
            (
                "AURX Acid Cross Heavy Thermal - Pitch Black",
                "aurx-acid-cross-heavy-thermal-pitch-black",
                "Hoodies & Sweatshirts",
                1599,
                3199,
                "BESTSELLER",
                "M,L,XL,XXL",
                "Pitch black heavyweight waffle thermal sweatshirt featuring iconic distressed acid-lime Maltese cross front graphic and gothic sleeve calligraphy. Engineered with tailored drop-shoulder cut.",
                "400 GSM Heavyweight Waffle Cotton, Vintage Acid Wash Finish, Pre-Shrunk, Double-Needle Stitched Hem",
                json.dumps(["/static/uploads/aurx_acid_cross_black.jpg"]),
                1,
                1
            ),
            (
                "AURX Duende Axolotl Thermal - Ecru Cream",
                "aurx-duende-axolotl-thermal-ecru-cream",
                "Hoodies & Sweatshirts",
                1499,
                2999,
                "TRENDING",
                "M,L,XL,XXL",
                "Off-white / cream heavyweight thermal waffle sweatshirt with dual circular dragon axolotl screenprint in crimson red and black, framed by barbed flame sleeve graphics.",
                "380 GSM Heavyweight Waffle Knit, 100% Combed Cotton, Ribbed Mock Collar, Reactive Pigment Dyed",
                json.dumps(["/static/uploads/aurx_duende_dragon_cream.jpg"]),
                1,
                1
            ),
            (
                "AURX Gothic Cross 777 Thermal - Deep Maroon",
                "aurx-gothic-cross-777-thermal-deep-maroon",
                "Hoodies & Sweatshirts",
                1499,
                2999,
                "NEW DROP",
                "M,L,XL,XXL",
                "Burgundy maroon thermal knit sweatshirt with cyan blue gothic cross and script scripture chest print, highlighted with angel number '777' sleeve graphics.",
                "380 GSM Premium Thermal Waffle Weave, Cyan High-Density Silkscreen, Anti-Shrink Wash",
                json.dumps(["/static/uploads/aurx_gothic_cross_maroon.jpg"]),
                1,
                1
            ),
            (
                "AURX Praying Hands Rosary Thermal - Crimson Red",
                "aurx-praying-hands-rosary-thermal-crimson-red",
                "Hoodies & Sweatshirts",
                1599,
                3199,
                "LIMITED DROP",
                "M,L,XL,XXL",
                "Statement crimson red thermal long-sleeve sweatshirt with vintage woodcut Praying Hands, crucifix rosary, and gothic scripture lettering on sleeves.",
                "380 GSM Heavy Combed Cotton Waffle Knit, Deep Crimson Reactive Dye, Double Ribbed Cuffs",
                json.dumps(["/static/uploads/aurx_praying_hands_red.jpg"]),
                1,
                1
            ),
            (
                "AURX Misery Club Racing Thermal - Optic White",
                "aurx-misery-club-racing-thermal-optic-white",
                "Hoodies & Sweatshirts",
                1499,
                2999,
                "MOTORSPORT",
                "M,L,XL,XXL",
                "Clean optic white thermal racing sweatshirt with multi-color Misery Club racing team graphics, checkered speed flags, number 1 emblem, and racing typography.",
                "380 GSM Heavyweight Thermal Weave, Multi-Color Plastisol Print, Reinforced Drop Shoulder Fit",
                json.dumps(["/static/uploads/aurx_misery_racing_white.jpg"]),
                1,
                1
            ),
            (
                "AURX Warstudios Dagger Skull Thermal - Charcoal",
                "aurx-warstudios-dagger-skull-thermal-charcoal",
                "Hoodies & Sweatshirts",
                1599,
                3199,
                "EXCLUSIVE",
                "M,L,XL,XXL",
                "Washed charcoal thermal sweatshirt featuring lavender purple skull biting tactical combat dagger, 'Warstudios Worldwide' banner, and gothic sleeve crossbones.",
                "400 GSM Ultra-Heavy Vintage Washed Waffle Cotton, Soft Brushed Feel, Raw Edge Bottom Hem",
                json.dumps(["/static/uploads/aurx_warstudios_skull_charcoal.jpg"]),
                1,
                1
            ),
            (
                "AURX Acid Cross Heavy Thermal - Heather Grey",
                "aurx-acid-cross-heavy-thermal-heather-grey",
                "Hoodies & Sweatshirts",
                1599,
                3199,
                "SIGNATURE",
                "M,L,XL,XXL",
                "Heather grey thermal knit sweatshirt featuring neon lime distressed Maltese cross artwork and sleeve calligraphic detailing. Boxy oversized streetwear cut.",
                "400 GSM Melange Thermal Cotton, Raw Edge Detailing, Reinforced Seams",
                json.dumps(["/static/uploads/aurx_acid_cross_grey.jpg"]),
                1,
                1
            )
        ]
        cursor.executemany("""
        INSERT INTO products (title, slug, category, price, original_price, badge, sizes, description, fabric_details, images, is_featured, in_stock)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_products)

    # Seed realistic initial orders if empty so admin has rich sales statistics
    cursor.execute("SELECT COUNT(*) FROM orders")
    if cursor.fetchone()[0] == 0:
        sample_orders = [
            ("AURX-10842", "Aryan Sharma", "9820194820", "aryan.sharma@gmail.com", "Flat 402, Sea Green Heights, Bandra West", "Mumbai", "Maharashtra", 1, "Cyber Chrome Heavyweight Tee", "/static/images/cat_tshirts_hd.jpg", "L", 2, 999, 1998, "Prepaid UPI", "Delivered", "Verified courier delivery with signature", "2026-11-14 11:20:00", "2026-11-17 14:10:00"),
            ("AURX-10843", "Dheeraj Gurjar", "7851891611", "dheerajgurjar7788@gmail.com", "Plot 12, Malviya Nagar", "Jaipur", "Rajasthan", 2, "Obsidian Acid Wash Boxy Hoodie", "/static/images/cat_hoodies_hd.jpg", "XL", 1, 1899, 1899, "WhatsApp / UPI", "Delivered", "Delivered on schedule", "2026-11-15 14:35:00", "2026-11-18 16:45:00"),
            ("AURX-10844", "Kabir Mehra", "9811223344", "kabir.mehra@outlook.com", "D-54, Hauz Khas", "New Delhi", "Delhi", 3, "Phantom Tactical Cargo Pants", "/static/images/cat_pants_hd.jpg", "M", 1, 1499, 1499, "COD", "Delivered", "Cash collected on delivery", "2026-11-16 09:15:00", "2026-11-19 12:30:00"),
            ("AURX-10845", "Rohan Verma", "9723456789", "rohan.v@gmail.com", "14th Main, Indiranagar", "Bengaluru", "Karnataka", 1, "Cyber Chrome Heavyweight Tee", "/static/images/cat_tshirts_hd.jpg", "M", 1, 999, 999, "Prepaid UPI", "Delivered", "Fast delivery", "2026-11-16 16:40:00", "2026-11-19 17:00:00"),
            ("AURX-10846", "Priya Nair", "9895012345", "priya.nair@yahoo.com", "Tower 3, Prestige Palms", "Kochi", "Kerala", 5, "Matrix Utility Bomber Jacket", "https://images.unsplash.com/photo-1548883354-7622d03aca27?auto=format&fit=crop&w=900&q=80", "M", 1, 2499, 2499, "Prepaid UPI", "Dispatched", "In transit via Bluedart AWB# 8492049", "2026-11-18 10:20:00", "2026-11-19 08:30:00"),
            ("AURX-10847", "Vikram Rathore", "9414056789", "vikram.rathore@gmail.com", "B-22, Shastri Nagar", "Jodhpur", "Rajasthan", 2, "Obsidian Acid Wash Boxy Hoodie", "/static/images/cat_hoodies_hd.jpg", "L", 1, 1899, 1899, "WhatsApp / UPI", "Dispatched", "Dispatched today morning", "2026-11-18 15:10:00", "2026-11-19 11:00:00"),
            ("AURX-10848", "Sameer Sen", "9830098765", "sameer.sen@gmail.com", "Salt Lake Sector 5", "Kolkata", "West Bengal", 3, "Phantom Tactical Cargo Pants", "/static/images/cat_pants_hd.jpg", "L", 2, 1499, 2998, "Prepaid UPI", "Processing", "Packing at central warehouse", "2026-11-19 18:22:00", "2026-11-19 18:22:00"),
            ("AURX-10849", "Aditya Kulkarni", "9822011223", "aditya.k@gmail.com", "Koregaon Park Lane 7", "Pune", "Maharashtra", 4, "Starlight Retro Acid Tee", "/static/images/cat_shirts_hd.jpg", "XL", 1, 1099, 1099, "WhatsApp / UPI", "Confirmed", "Payment verified via WhatsApp screenshot", "2026-11-20 11:05:00", "2026-11-20 11:05:00"),
            ("AURX-10850", "Tanmay Bhatia", "9871122334", "tanmay.bhatia@gmail.com", "Golf Course Road, Sector 54", "Gurugram", "Haryana", 2, "Obsidian Acid Wash Boxy Hoodie", "/static/images/cat_hoodies_hd.jpg", "XXL", 1, 1899, 1899, "Prepaid UPI", "Confirmed", "Fresh order received", "2026-11-20 13:40:00", "2026-11-20 13:40:00"),
            ("AURX-10851", "Hardik Patel", "9825067890", "hardik.patel@gmail.com", "SG Highway, Bodakdev", "Ahmedabad", "Gujarat", 1, "Cyber Chrome Heavyweight Tee", "/static/images/cat_tshirts_hd.jpg", "L", 3, 999, 2997, "Prepaid UPI", "Confirmed", "Express courier packaging requested", "2026-11-20 17:15:00", "2026-11-20 17:15:00"),
            ("AURX-10852", "Siddharth Roy", "9845012399", "sid.roy@gmail.com", "Koramangala 4th Block", "Bengaluru", "Karnataka", 3, "Phantom Tactical Cargo Pants", "/static/images/cat_pants_hd.jpg", "XL", 1, 1499, 1499, "WhatsApp / UPI", "Returned", "Customer requested exchange for size L", "2026-11-12 10:00:00", "2026-11-16 12:00:00"),
        ]
        cursor.executemany("""
        INSERT INTO orders (order_number, customer_name, customer_phone, customer_email, shipping_address, city, state, product_id, product_title, product_image, size, quantity, unit_price, total_price, payment_method, status, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_orders)

    # Seed realistic returns if empty
    cursor.execute("SELECT COUNT(*) FROM returns")
    if cursor.fetchone()[0] == 0:
        sample_returns = [
            ("RET-4091", 11, "AURX-10852", "Siddharth Roy", "9845012399", "Phantom Tactical Cargo Pants", "XL", 1499, "Size too large (Requested L size replacement)", "Refund Issued", "Original amount refunded to UPI ID sid.roy@oksbi. Replacement order dispatched.", "2026-11-15 14:00:00", "2026-11-16 11:30:00"),
            ("RET-4092", 3, "AURX-10844", "Kabir Mehra", "9811223344", "Phantom Tactical Cargo Pants", "M", 1499, "Ankle bungee stopper tight fit", "Approved - Pickup Scheduled", "Pickup booked via Delhivery for 21 Nov 2026", "2026-11-19 16:20:00", "2026-11-20 10:00:00"),
            ("RET-4093", 4, "AURX-10845", "Rohan Verma", "9723456789", "Cyber Chrome Heavyweight Tee", "M", 999, "Ordered wrong color by mistake", "Pending Review", "Customer contacted on WhatsApp, reviewing return policy eligibility", "2026-11-20 14:15:00", "2026-11-20 14:15:00")
        ]
        cursor.executemany("""
        INSERT INTO returns (return_number, order_id, order_number, customer_name, customer_phone, product_title, size, amount, reason, status, admin_notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_returns)

    # Seed initial traffic if empty so charts and numbers are informative immediately
    cursor.execute("SELECT COUNT(*) FROM site_visits")
    if cursor.fetchone()[0] == 0:
        base_time = datetime.now()
        initial_visits = []
        for i in range(120):
            delta = timedelta(hours=i*1.5)
            visit_time = (base_time - delta).strftime("%Y-%m-%d %H:%M:%S")
            dev = "Mobile" if (i % 3 != 0) else "Desktop"
            page = "/" if (i % 2 == 0) else "/product/cyber-chrome-heavyweight-tee" if (i % 4 == 1) else "/product/obsidian-acid-wash-boxy-hoodie"
            initial_visits.append((
                f"vis_{i%40}",
                f"ip_hash_{i%30}",
                page,
                "AURX WEAR Streetwear Store",
                "Direct / Instagram",
                dev,
                "Chrome Mobile" if dev == "Mobile" else "Chrome Desktop",
                "India",
                visit_time
            ))
        cursor.executemany("""
        INSERT INTO site_visits (visitor_id, ip_hash, page_url, page_title, referrer, device_type, browser, country, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_visits)

    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# SETTINGS & STORE PROFILE
# ---------------------------------------------------------------------------

def get_settings():
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {}

def update_settings(data):
    conn = get_db_connection()
    conn.execute("""
    UPDATE settings SET
        store_name = :store_name,
        tagline = :tagline,
        whatsapp_number = :whatsapp_number,
        email = :email,
        currency_symbol = :currency_symbol,
        announcement_text = :announcement_text,
        instagram_url = :instagram_url,
        banner_subtitle = :banner_subtitle
    WHERE id = 1
    """, data)
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# ADMIN AUTHENTICATION, PASSWORD HASHING & BRUTE-FORCE SECURITY
# ---------------------------------------------------------------------------

def check_admin_password(password: str) -> bool:
    """Check password against PBKDF2 hash stored in database."""
    settings = get_settings()
    stored_hash = settings.get("admin_password")
    return verify_password(password, stored_hash)

def update_admin_password(new_password: str):
    """Hash and securely store the new admin password."""
    new_hash = hash_password(new_password)
    conn = get_db_connection()
    conn.execute("UPDATE settings SET admin_password = ? WHERE id = 1", (new_hash,))
    conn.commit()
    conn.close()

def is_ip_locked(ip_address: str) -> bool:
    """Check if an IP has had >= 5 failed login attempts in the last 15 minutes."""
    conn = get_db_connection()
    time_threshold = (datetime.now() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.cursor()
    cursor.execute("""
    SELECT COUNT(*) FROM login_attempts 
    WHERE ip_address = ? AND attempted_at >= ? AND success = 0
    """, (ip_address, time_threshold))
    count = cursor.fetchone()[0]
    conn.close()
    return count >= 5

def record_login_attempt(ip_address: str, success: bool):
    """Record login attempt for rate-limiting and audit logging."""
    conn = get_db_connection()
    conn.execute("""
    INSERT INTO login_attempts (ip_address, success)
    VALUES (?, ?)
    """, (ip_address, 1 if success else 0))
    # If successful login, clear older failed attempts for this IP
    if success:
        conn.execute("DELETE FROM login_attempts WHERE ip_address = ? AND success = 0", (ip_address,))
    conn.commit()
    conn.close()

def create_admin_session(session_token: str, ip_address: str = "", user_agent: str = "", max_age_seconds: int = 86400 * 7):
    """Store cryptographically generated session token with expiry timestamp."""
    expires_at = (datetime.now() + timedelta(seconds=max_age_seconds)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    conn.execute("""
    INSERT OR REPLACE INTO admin_sessions (session_token, ip_address, user_agent, expires_at)
    VALUES (?, ?, ?, ?)
    """, (session_token, ip_address, user_agent, expires_at))
    conn.commit()
    conn.close()

def is_session_valid(session_token: str) -> bool:
    """Validate session token against database and check expiration."""
    if not session_token:
        return False
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = conn.execute("""
    SELECT session_token FROM admin_sessions 
    WHERE session_token = ? AND expires_at > ?
    """, (session_token, now_str)).fetchone()
    conn.close()
    return row is not None

def delete_admin_session(session_token: str):
    """Invalidate session token immediately upon logout."""
    if not session_token:
        return
    conn = get_db_connection()
    conn.execute("DELETE FROM admin_sessions WHERE session_token = ?", (session_token,))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# SALES, ORDERS & RETURNS MANAGEMENT
# ---------------------------------------------------------------------------

def create_order(data: dict) -> str:
    """Create a new order and return the unique order number."""
    conn = get_db_connection()
    order_number = data.get("order_number")
    if not order_number:
        rand_num = secrets.randbelow(90000) + 10000
        order_number = f"AURX-{rand_num}"

    total_price = int(data.get("total_price", 0)) or (int(data.get("unit_price", 0)) * int(data.get("quantity", 1)))
    
    conn.execute("""
    INSERT INTO orders (
        order_number, customer_name, customer_phone, customer_email,
        shipping_address, city, state, product_id, product_title, product_image,
        size, quantity, unit_price, total_price, payment_method, status, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_number,
        data.get("customer_name", "Valued Customer"),
        data.get("customer_phone", ""),
        data.get("customer_email", ""),
        data.get("shipping_address", ""),
        data.get("city", ""),
        data.get("state", ""),
        data.get("product_id"),
        data.get("product_title", "Streetwear Essential"),
        data.get("product_image", "/static/images/logo.jpg"),
        data.get("size", "L"),
        int(data.get("quantity", 1)),
        int(data.get("unit_price", 0)),
        total_price,
        data.get("payment_method", "WhatsApp / UPI"),
        data.get("status", "Confirmed"),
        data.get("notes", "")
    ))
    conn.commit()
    conn.close()
    return order_number

def get_all_orders(status_filter=None, search=None, limit=100):
    conn = get_db_connection()
    query = "SELECT * FROM orders WHERE 1=1"
    params = []

    if status_filter and status_filter.lower() != 'all':
        query += " AND LOWER(status) = LOWER(?)"
        params.append(status_filter)

    if search:
        query += " AND (order_number LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ? OR product_title LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_order_by_id(order_id: int):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_order_status(order_id: int, new_status: str, notes: str = None):
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if notes is not None:
        conn.execute("""
        UPDATE orders SET status = ?, notes = ?, updated_at = ? WHERE id = ?
        """, (new_status, notes, now_str, order_id))
    else:
        conn.execute("""
        UPDATE orders SET status = ?, updated_at = ? WHERE id = ?
        """, (new_status, now_str, order_id))
    conn.commit()
    conn.close()

def delete_order(order_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

def create_return_request(data: dict) -> str:
    """Create a new return request ticket and return the return number."""
    conn = get_db_connection()
    return_number = data.get("return_number")
    if not return_number:
        rand_num = secrets.randbelow(9000) + 1000
        return_number = f"RET-{rand_num}"

    conn.execute("""
    INSERT INTO returns (
        return_number, order_id, order_number, customer_name, customer_phone,
        product_title, size, amount, reason, status, admin_notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        return_number,
        data.get("order_id", 0),
        data.get("order_number", ""),
        data.get("customer_name", ""),
        data.get("customer_phone", ""),
        data.get("product_title", ""),
        data.get("size", ""),
        int(data.get("amount", 0)),
        data.get("reason", "Size / Fit issue"),
        data.get("status", "Pending Review"),
        data.get("admin_notes", "")
    ))
    conn.commit()
    conn.close()
    return return_number

def get_all_returns(status_filter=None, search=None):
    conn = get_db_connection()
    query = "SELECT * FROM returns WHERE 1=1"
    params = []

    if status_filter and status_filter.lower() != 'all':
        query += " AND LOWER(status) = LOWER(?)"
        params.append(status_filter)

    if search:
        query += " AND (return_number LIKE ? OR order_number LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    query += " ORDER BY id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_return_status(return_id: int, new_status: str, admin_notes: str = None):
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if admin_notes is not None:
        conn.execute("""
        UPDATE returns SET status = ?, admin_notes = ?, updated_at = ? WHERE id = ?
        """, (new_status, admin_notes, now_str, return_id))
    else:
        conn.execute("""
        UPDATE returns SET status = ?, updated_at = ? WHERE id = ?
        """, (new_status, now_str, return_id))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# VISITOR TRAFFIC & ANALYTICS LOGGING
# ---------------------------------------------------------------------------

def record_site_visit(visitor_id: str, ip_hash: str, page_url: str, page_title: str = "", referrer: str = "", device_type: str = "Desktop", browser: str = "Chrome"):
    """Record an individual public page visit."""
    try:
        conn = get_db_connection()
        conn.execute("""
        INSERT INTO site_visits (visitor_id, ip_hash, page_url, page_title, referrer, device_type, browser, country)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'India')
        """, (visitor_id, ip_hash, page_url, page_title, referrer, device_type, browser))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error recording visit: {e}")

def record_inquiry(channel: str, product_title: str = "", customer_name: str = "", customer_contact: str = "", message: str = ""):
    """Record a concierge or WhatsApp inquiry lead."""
    try:
        conn = get_db_connection()
        conn.execute("""
        INSERT INTO leads_and_inquiries (channel, product_title, customer_name, customer_contact, message)
        VALUES (?, ?, ?, ?, ?)
        """, (channel, product_title, customer_name, customer_contact, message))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error recording inquiry: {e}")

def get_all_inquiries(limit: int = 50):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM leads_and_inquiries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ---------------------------------------------------------------------------
# COMPREHENSIVE DASHBOARD METRICS & ANALYTICS
# ---------------------------------------------------------------------------

def get_dashboard_analytics():
    """Aggregate all critical sales, returns, and visitor traffic metrics."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Total Sales Metrics (Orders not cancelled)
    cursor.execute("""
    SELECT 
        COALESCE(SUM(total_price), 0) AS total_revenue,
        COUNT(*) AS total_orders,
        COALESCE(AVG(total_price), 0) AS aov
    FROM orders 
    WHERE status != 'Cancelled'
    """)
    sales_row = cursor.fetchone()
    total_revenue = sales_row["total_revenue"]
    total_orders = sales_row["total_orders"]
    aov = round(sales_row["aov"])

    # Delivered vs Active vs Cancelled counts
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'Delivered'")
    delivered_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status IN ('Confirmed', 'Processing', 'Dispatched')")
    active_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'Cancelled'")
    cancelled_orders = cursor.fetchone()[0]

    # Today's Sales
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
    SELECT 
        COALESCE(SUM(total_price), 0) AS today_rev,
        COUNT(*) AS today_count
    FROM orders 
    WHERE created_at LIKE ? AND status != 'Cancelled'
    """, (f"{today_prefix}%",))
    today_sales_row = cursor.fetchone()
    today_revenue = today_sales_row["today_rev"]
    today_orders = today_sales_row["today_count"]

    # 2. Returns Metrics
    cursor.execute("""
    SELECT 
        COALESCE(SUM(amount), 0) AS total_returns_amount,
        COUNT(*) AS total_returns_count
    FROM returns
    """)
    ret_row = cursor.fetchone()
    total_returns_amount = ret_row["total_returns_amount"]
    total_returns_count = ret_row["total_returns_count"]

    cursor.execute("SELECT COUNT(*) FROM returns WHERE status = 'Pending Review'")
    pending_returns_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM returns WHERE status = 'Refund Issued'")
    refunded_returns_count = cursor.fetchone()[0]

    return_rate = round((total_returns_count / total_orders * 100), 1) if total_orders > 0 else 0.0

    # 3. Traffic & Visitor Analytics
    cursor.execute("SELECT COUNT(*) FROM site_visits")
    total_page_views = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT visitor_id) FROM site_visits")
    total_unique_visitors = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT visitor_id) FROM site_visits WHERE created_at LIKE ?", (f"{today_prefix}%",))
    today_unique_visitors = cursor.fetchone()[0]

    # Device Breakdown
    cursor.execute("SELECT COUNT(*) FROM site_visits WHERE device_type = 'Mobile'")
    mobile_visits = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM site_visits WHERE device_type = 'Desktop'")
    desktop_visits = cursor.fetchone()[0]

    mobile_pct = round((mobile_visits / total_page_views * 100)) if total_page_views > 0 else 65
    desktop_pct = 100 - mobile_pct if total_page_views > 0 else 35

    # Top Visited Pages
    cursor.execute("""
    SELECT page_url, COUNT(*) as views 
    FROM site_visits 
    GROUP BY page_url 
    ORDER BY views DESC 
    LIMIT 5
    """)
    top_pages = [dict(r) for r in cursor.fetchall()]

    # Recent 10 Visits
    cursor.execute("""
    SELECT page_url, device_type, browser, created_at 
    FROM site_visits 
    ORDER BY id DESC 
    LIMIT 10
    """)
    recent_visits = [dict(r) for r in cursor.fetchall()]

    # Recent 5 Orders
    cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 5")
    recent_orders = [dict(r) for r in cursor.fetchall()]

    # Recent 5 Returns
    cursor.execute("SELECT * FROM returns ORDER BY id DESC LIMIT 5")
    recent_returns = [dict(r) for r in cursor.fetchall()]

    # Top Selling Products
    cursor.execute("""
    SELECT product_title, COUNT(*) as orders_count, SUM(total_price) as total_val
    FROM orders 
    WHERE status != 'Cancelled'
    GROUP BY product_title 
    ORDER BY orders_count DESC 
    LIMIT 5
    """)
    top_products_sold = [dict(r) for r in cursor.fetchall()]

    # Total products and inventory stats
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products WHERE in_stock = 1")
    in_stock_count = cursor.fetchone()[0]
    out_of_stock_count = total_products - in_stock_count

    conn.close()

    return {
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "aov": aov,
        "delivered_orders": delivered_orders,
        "active_orders": active_orders,
        "cancelled_orders": cancelled_orders,
        "today_revenue": today_revenue,
        "today_orders": today_orders,
        "total_returns_amount": total_returns_amount,
        "total_returns_count": total_returns_count,
        "pending_returns_count": pending_returns_count,
        "refunded_returns_count": refunded_returns_count,
        "return_rate": return_rate,
        "total_page_views": total_page_views,
        "total_unique_visitors": total_unique_visitors,
        "today_unique_visitors": today_unique_visitors,
        "mobile_pct": mobile_pct,
        "desktop_pct": desktop_pct,
        "top_pages": top_pages,
        "recent_visits": recent_visits,
        "recent_orders": recent_orders,
        "recent_returns": recent_returns,
        "top_products_sold": top_products_sold,
        "total_products": total_products,
        "in_stock_count": in_stock_count,
        "out_of_stock_count": out_of_stock_count,
    }

# ---------------------------------------------------------------------------
# CATEGORIES & PRODUCT CRUD (EXISTING PRESERVED & EXTENDED)
# ---------------------------------------------------------------------------

def get_all_categories():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM categories ORDER BY display_order ASC, name ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_category(name):
    slug = slugify(name)
    conn = get_db_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO categories (name, slug) VALUES (?, ?)", (name, slug))
        conn.commit()
    finally:
        conn.close()

def get_all_products(category=None, search=None, sort=None):
    conn = get_db_connection()
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if category and category.lower() != 'all':
        query += " AND (LOWER(category) = LOWER(?) OR slug = ?)"
        params.extend([category, category])

    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR category LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])

    if sort == "price_low":
        query += " ORDER BY price ASC"
    elif sort == "price_high":
        query += " ORDER BY price DESC"
    else:
        query += " ORDER BY is_featured DESC, id DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    products = []
    for r in rows:
        p = dict(r)
        try:
            p['image_list'] = json.loads(p['images'])
        except:
            p['image_list'] = [p['images']] if p['images'] else []
        if not p['image_list']:
            p['image_list'] = ["/static/images/logo.jpg"]
        p['primary_image'] = p['image_list'][0] if p['image_list'] else "/static/images/logo.jpg"
        
        if p['original_price'] and p['original_price'] > p['price']:
            p['discount_pct'] = round(((p['original_price'] - p['price']) / p['original_price']) * 100)
        else:
            p['discount_pct'] = 0
            
        p['size_list'] = [s.strip() for s in p['sizes'].split(',') if s.strip()]
        products.append(p)
    return products

def get_product_by_id(product_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if not row:
        return None
    p = dict(row)
    try:
        p['image_list'] = json.loads(p['images'])
    except:
        p['image_list'] = [p['images']] if p['images'] else []
    if not p['image_list']:
        p['image_list'] = ["/static/images/logo.jpg"]
    p['primary_image'] = p['image_list'][0]
    if p['original_price'] and p['original_price'] > p['price']:
        p['discount_pct'] = round(((p['original_price'] - p['price']) / p['original_price']) * 100)
    else:
        p['discount_pct'] = 0
    p['size_list'] = [s.strip() for s in p['sizes'].split(',') if s.strip()]
    return p

def get_product_by_slug(slug):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM products WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    if not row:
        return None
    p = dict(row)
    try:
        p['image_list'] = json.loads(p['images'])
    except:
        p['image_list'] = [p['images']] if p['images'] else []
    if not p['image_list']:
        p['image_list'] = ["/static/images/logo.jpg"]
    p['primary_image'] = p['image_list'][0]
    if p['original_price'] and p['original_price'] > p['price']:
        p['discount_pct'] = round(((p['original_price'] - p['price']) / p['original_price']) * 100)
    else:
        p['discount_pct'] = 0
    p['size_list'] = [s.strip() for s in p['sizes'].split(',') if s.strip()]
    return p

def add_product(data):
    conn = get_db_connection()
    base_slug = slugify(data['title'])
    slug = base_slug
    counter = 1
    while conn.execute("SELECT 1 FROM products WHERE slug = ?", (slug,)).fetchone():
        slug = f"{base_slug}-{counter}"
        counter += 1

    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO products (title, slug, category, price, original_price, badge, sizes, description, fabric_details, images, is_featured, in_stock)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['title'],
        slug,
        data['category'],
        int(data['price']),
        int(data.get('original_price', 0) or 0),
        data.get('badge', ''),
        data.get('sizes', 'S,M,L,XL'),
        data.get('description', ''),
        data.get('fabric_details', ''),
        json.dumps(data.get('images', [])),
        int(data.get('is_featured', 0)),
        int(data.get('in_stock', 1))
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def update_product(product_id, data):
    conn = get_db_connection()
    conn.execute("""
    UPDATE products SET
        title = :title,
        category = :category,
        price = :price,
        original_price = :original_price,
        badge = :badge,
        sizes = :sizes,
        description = :description,
        fabric_details = :fabric_details,
        images = :images,
        is_featured = :is_featured,
        in_stock = :in_stock
    WHERE id = :id
    """, {
        'id': product_id,
        'title': data['title'],
        'category': data['category'],
        'price': int(data['price']),
        'original_price': int(data.get('original_price', 0) or 0),
        'badge': data.get('badge', ''),
        'sizes': data.get('sizes', 'S,M,L,XL'),
        'description': data.get('description', ''),
        'fabric_details': data.get('fabric_details', ''),
        'images': json.dumps(data.get('images', [])),
        'is_featured': int(data.get('is_featured', 0)),
        'in_stock': int(data.get('in_stock', 1))
    })
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

def toggle_product_stock(product_id):
    conn = get_db_connection()
    row = conn.execute("SELECT in_stock FROM products WHERE id = ?", (product_id,)).fetchone()
    if row:
        new_status = 0 if row['in_stock'] == 1 else 1
        conn.execute("UPDATE products SET in_stock = ? WHERE id = ?", (new_status, product_id))
        conn.commit()
    conn.close()
