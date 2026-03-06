"""
Sizzle — Full Database Seed Script
====================================
1. Drops & recreates all tables (clean slate)
2. Seeds 2 restaurants with full data:
   - Restaurant 1: Spice Craft (Indian Multi-Cuisine, 100 items)
   - Restaurant 2: Dragon Wok  (Chinese & Pan-Asian, 50 items)
3. Seeds ingredients + recipes (menu_item_ingredients)
4. Seeds 200 historical orders per restaurant (past 90 days)
5. Logs stock usage from those orders

Run from backend/ folder:
    python seed_database.py
"""

import os, sys, random, hashlib, string, json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("psycopg2 not found. Installing...")
    os.system(f"{sys.executable} -m pip install psycopg2-binary")
    import psycopg2
    from psycopg2.extras import execute_values

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)

# ─────────────────────────── helpers ────────────────────────────

def h(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def uid(n=6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))

def now_utc():
    return datetime.now(timezone.utc)

def rand_dt(days_ago_max=90, days_ago_min=1):
    delta = timedelta(
        days=random.randint(days_ago_min, days_ago_max),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return now_utc() - delta

# ──────────────────────────── DDL ───────────────────────────────

DDL = """
-- ══════════════════ DROP EVERYTHING ══════════════════
DROP VIEW  IF EXISTS v_sales CASCADE;
DROP TABLE IF EXISTS stock_logs CASCADE;
DROP TABLE IF EXISTS menu_item_ingredients CASCADE;
DROP TABLE IF EXISTS ingredients CASCADE;
DROP TABLE IF EXISTS combo_suggestions CASCADE;
DROP TABLE IF EXISTS voice_sessions CASCADE;
DROP TABLE IF EXISTS kots CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS restaurant_tables CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS menu_items CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS restaurant_settings CASCADE;
DROP TABLE IF EXISTS restaurants CASCADE;

DROP TYPE IF EXISTS table_status CASCADE;
DROP TYPE IF EXISTS order_status CASCADE;
DROP TYPE IF EXISTS order_type CASCADE;
DROP TYPE IF EXISTS order_source CASCADE;
DROP TYPE IF EXISTS payment_method CASCADE;
DROP TYPE IF EXISTS stock_reason CASCADE;
DROP TYPE IF EXISTS measure_unit CASCADE;

-- ══════════════════ ENUM TYPES ══════════════════
CREATE TYPE table_status   AS ENUM ('empty','occupied','reserved','cleaning');
CREATE TYPE order_status   AS ENUM ('building','confirmed','cancelled');
CREATE TYPE order_type     AS ENUM ('dine_in','takeaway','delivery');
CREATE TYPE order_source   AS ENUM ('voice','manual');
CREATE TYPE payment_method AS ENUM ('cash','card','upi');
CREATE TYPE stock_reason   AS ENUM ('purchase','usage','waste','adjustment');
CREATE TYPE measure_unit   AS ENUM ('g','kg','ml','L','pcs');

-- ══════════════════ TABLES ══════════════════

CREATE TABLE restaurants (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(200)  NOT NULL,
    slug          VARCHAR(100)  UNIQUE NOT NULL,
    email         VARCHAR(200)  UNIQUE NOT NULL,
    password_hash VARCHAR(256)  NOT NULL,
    phone         VARCHAR(20),
    address       TEXT,
    cuisine_type  VARCHAR(100),
    logo_url      VARCHAR(500),
    is_active     BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_restaurants_active ON restaurants (id) WHERE is_active;

CREATE TABLE restaurant_settings (
    id              SERIAL PRIMARY KEY,
    restaurant_id   INTEGER NOT NULL UNIQUE REFERENCES restaurants(id) ON DELETE CASCADE,
    menu_management JSONB NOT NULL DEFAULT '{}',
    notifications   JSONB NOT NULL DEFAULT '{}',
    integrations    JSONB NOT NULL DEFAULT '{}',
    billing_plan    JSONB NOT NULL DEFAULT '{}',
    security        JSONB NOT NULL DEFAULT '{}',
    voice_ai_config JSONB NOT NULL DEFAULT '{}',
    profile_extras  JSONB NOT NULL DEFAULT '{}',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE categories (
    id            SERIAL PRIMARY KEY,
    restaurant_id INTEGER      NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name          VARCHAR(100) NOT NULL,
    name_hi       VARCHAR(100),
    name_mr       VARCHAR(100),
    name_kn       VARCHAR(100),
    name_gu       VARCHAR(100),
    name_hi_en    VARCHAR(100),
    display_order SMALLINT     NOT NULL DEFAULT 0,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    UNIQUE (restaurant_id, name)
);
CREATE INDEX idx_categories_active ON categories (restaurant_id) WHERE is_active;

CREATE TABLE menu_items (
    id            SERIAL PRIMARY KEY,
    restaurant_id INTEGER       NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name          VARCHAR(200)  NOT NULL,
    name_hi       VARCHAR(200),
    name_mr       VARCHAR(200),
    name_kn       VARCHAR(200),
    name_gu       VARCHAR(200),
    name_hi_en    VARCHAR(200),
    description   TEXT,
    aliases       TEXT[]        NOT NULL DEFAULT '{}',
    category_id   INTEGER       REFERENCES categories(id) ON DELETE SET NULL,
    selling_price NUMERIC(10,2) NOT NULL,
    food_cost     NUMERIC(10,2) NOT NULL,
    modifiers     JSONB         NOT NULL DEFAULT '{}',
    is_veg        BOOLEAN       NOT NULL DEFAULT TRUE,
    is_available  BOOLEAN       NOT NULL DEFAULT TRUE,
    is_bestseller BOOLEAN       NOT NULL DEFAULT FALSE,
    current_stock INTEGER,
    tags          JSONB         NOT NULL DEFAULT '[]',
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_mi_restaurant ON menu_items (restaurant_id);
CREATE INDEX idx_mi_category   ON menu_items (category_id);
CREATE INDEX idx_mi_available  ON menu_items (restaurant_id, category_id) WHERE is_available;
CREATE INDEX idx_mi_tags       ON menu_items USING GIN (tags);

CREATE TABLE restaurant_tables (
    id               SERIAL PRIMARY KEY,
    restaurant_id    INTEGER      NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    table_number     VARCHAR(10)  NOT NULL,
    capacity         SMALLINT     NOT NULL DEFAULT 4,
    section          VARCHAR(50)  NOT NULL DEFAULT 'main',
    status           table_status NOT NULL DEFAULT 'empty',
    current_order_id INTEGER,
    UNIQUE (restaurant_id, table_number)
);
CREATE INDEX idx_tables_restaurant ON restaurant_tables (restaurant_id);
CREATE INDEX idx_tables_occupied   ON restaurant_tables (restaurant_id) WHERE status = 'occupied';

CREATE TABLE orders (
    id             SERIAL PRIMARY KEY,
    restaurant_id  INTEGER         NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    order_id       VARCHAR(50)     UNIQUE NOT NULL,
    order_number   VARCHAR(20),
    total_amount   NUMERIC(10,2)   NOT NULL DEFAULT 0,
    status         order_status    NOT NULL DEFAULT 'building',
    order_type     order_type      NOT NULL DEFAULT 'dine_in',
    table_id       INTEGER         REFERENCES restaurant_tables(id) ON DELETE SET NULL,
    source         order_source    NOT NULL DEFAULT 'manual',
    guest_name     VARCHAR(150),
    guest_count    SMALLINT,
    payment_method payment_method,
    settled_at     TIMESTAMPTZ,
    created_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
ALTER TABLE restaurant_tables
    ADD CONSTRAINT fk_tables_current_order
    FOREIGN KEY (current_order_id) REFERENCES orders(id) ON DELETE SET NULL;

CREATE INDEX idx_orders_restaurant ON orders (restaurant_id);
CREATE INDEX idx_orders_status     ON orders (restaurant_id, status);
CREATE INDEX idx_orders_building   ON orders (restaurant_id) WHERE status = 'building';
CREATE INDEX idx_orders_table      ON orders (table_id) WHERE table_id IS NOT NULL;
CREATE INDEX idx_orders_created    ON orders USING BRIN (created_at);

CREATE TABLE order_items (
    id                SERIAL PRIMARY KEY,
    order_pk          INTEGER       NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    item_id           INTEGER       NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    quantity          SMALLINT      NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price        NUMERIC(10,2) NOT NULL,
    modifiers_applied JSONB         NOT NULL DEFAULT '{}',
    line_total        NUMERIC(10,2) NOT NULL
);
CREATE INDEX idx_oi_order ON order_items (order_pk);
CREATE INDEX idx_oi_item  ON order_items (item_id);

CREATE TABLE kots (
    id            SERIAL PRIMARY KEY,
    kot_id        VARCHAR(50)  UNIQUE NOT NULL,
    order_pk      INTEGER      NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    items_summary JSONB        NOT NULL,
    print_ready   TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_kots_order ON kots (order_pk);

CREATE TABLE combo_suggestions (
    id               SERIAL PRIMARY KEY,
    restaurant_id    INTEGER       NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name             VARCHAR(200)  NOT NULL,
    item_ids         JSONB         NOT NULL,
    item_names       JSONB         NOT NULL,
    individual_total NUMERIC(10,2),
    combo_price      NUMERIC(10,2),
    discount_pct     NUMERIC(5,2),
    expected_margin  NUMERIC(10,2),
    support          REAL,
    confidence       REAL,
    lift             REAL,
    combo_score      REAL,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_combos_restaurant ON combo_suggestions (restaurant_id);
CREATE INDEX idx_combos_score      ON combo_suggestions (combo_score DESC NULLS LAST);
CREATE INDEX idx_combos_items      ON combo_suggestions USING GIN (item_ids);

CREATE TABLE ingredients (
    id            SERIAL PRIMARY KEY,
    restaurant_id INTEGER       NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name          VARCHAR(150)  NOT NULL,
    unit          measure_unit  NOT NULL DEFAULT 'g',
    current_stock NUMERIC(10,2) NOT NULL DEFAULT 0,
    reorder_level NUMERIC(10,2) NOT NULL DEFAULT 0,
    cost_per_unit NUMERIC(10,4) NOT NULL DEFAULT 0,
    is_active     BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (restaurant_id, name)
);
CREATE INDEX idx_ingredients_active ON ingredients (restaurant_id) WHERE is_active;
CREATE INDEX idx_ingredients_low    ON ingredients (restaurant_id)
                                    WHERE current_stock <= reorder_level AND is_active;

CREATE TABLE menu_item_ingredients (
    id            SERIAL PRIMARY KEY,
    menu_item_id  INTEGER       NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    ingredient_id INTEGER       NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity_used NUMERIC(10,4) NOT NULL,
    UNIQUE (menu_item_id, ingredient_id)
);
CREATE INDEX idx_mii_ingredient ON menu_item_ingredients (ingredient_id);

CREATE TABLE stock_logs (
    id            SERIAL PRIMARY KEY,
    ingredient_id INTEGER       NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    change_qty    NUMERIC(10,2) NOT NULL,
    reason        stock_reason  NOT NULL,
    note          TEXT,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_sl_ingredient ON stock_logs (ingredient_id);
CREATE INDEX idx_sl_created    ON stock_logs USING BRIN (created_at);
CREATE INDEX idx_sl_waste      ON stock_logs (ingredient_id) WHERE reason = 'waste';

CREATE TABLE voice_sessions (
    id          SERIAL PRIMARY KEY,
    session_id  VARCHAR(100) UNIQUE NOT NULL,
    last_active TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    order_items JSONB        NOT NULL DEFAULT '[]',
    last_items  JSONB        NOT NULL DEFAULT '[]',
    turn_count  SMALLINT     NOT NULL DEFAULT 0,
    confirmed   BOOLEAN      NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_vs_active ON voice_sessions (last_active);

-- ══════════════════ VIEW ══════════════════
CREATE OR REPLACE VIEW v_sales AS
SELECT
    oi.id                                AS id,
    o.restaurant_id                      AS restaurant_id,
    oi.item_id                           AS item_id,
    o.order_id                           AS order_id,
    oi.quantity                          AS quantity,
    oi.unit_price                        AS unit_price,
    oi.line_total                        AS total_price,
    o.order_type::TEXT                   AS order_type,
    COALESCE(o.settled_at, o.updated_at) AS sold_at
FROM order_items oi
JOIN orders o ON o.id = oi.order_pk
WHERE o.status = 'confirmed';
"""

# ──────────────────────── seed data ─────────────────────────────

RESTAURANT_1 = {
    "name": "Spice Craft",
    "slug": "spice-craft",
    "email": "admin@spicecraft.in",
    "password": "spicecraft123",
    "phone": "+91-9876543210",
    "address": "12, MG Road, Bengaluru, Karnataka 560001",
    "cuisine_type": "Indian Multi-Cuisine",
}

RESTAURANT_2 = {
    "name": "Dragon Wok",
    "slug": "dragon-wok",
    "email": "admin@dragonwok.in",
    "password": "dragon123",
    "phone": "+91-9123456780",
    "address": "45, Linking Road, Bandra West, Mumbai 400050",
    "cuisine_type": "Chinese & Pan-Asian",
}

# ══════════════════════════════════════════════════════════════════
#  R1 CATEGORIES & MENU ITEMS  (Spice Garden — North Indian)
# ══════════════════════════════════════════════════════════════════
# Category tuple: (name_hi, name_mr, name_kn, name_gu, name_hi_en, display_order)

R1_CATEGORIES = {
    "Starters":       ("स्टार्टर",        "स्टार्टर",        "ಸ್ಟಾರ್ಟರ್",       "સ્ટાર્ટર",       "Starter",            1),
    "Soups":          ("सूप",              "सूप",              "ಸೂಪ್",            "સૂપ",            "Soup",               2),
    "Roti & Naan":    ("रोटी और नान",      "रोटी आणि नान",    "ರೋಟಿ ಮತ್ತು ನಾನ್", "રોટી અને નાન",   "Roti aur Naan",      3),
    "Main Course":    ("मुख्य व्यंजन",    "मुख्य पदार्थ",    "ಮುಖ್ಯ ಊಟ",        "મુખ્ય વાનગી",    "Mukhya Vyanjan",     4),
    "Rice & Biryani": ("चावल और बिरयानी",  "भात आणि बिर्याणी","ಅನ್ನ ಮತ್ತು ಬಿರಿಯಾನಿ","ભાત અને બિરયાની","Chawal aur Biryani", 5),
    "Desserts":       ("मिठाई",            "गोड पदार्थ",      "ಸಿಹಿ ತಿನಿಸು",     "મીઠાઈ",          "Mithai",             6),
    "Beverages":      ("पेय पदार्थ",       "पेये",             "ಪಾನೀಯ",           "પીણાં",          "Pey Padarth",        7),
    "Salads & Raita": ("सलाद और रायता",    "सॅलड आणि रायता",  "ಸಲಾಡ್ ಮತ್ತು ರೈತಾ","સલાડ અને રાયતું", "Salad aur Raita",    8),
}

# Item tuple: (name, name_hi, name_mr, name_kn, name_gu, name_hi_en,
#              price, food_cost, is_veg, bestseller, [aliases], description)

R1_ITEMS = {
    "Starters": [
        ("Paneer Tikka",        "पनीर टिक्का",       "पनीर टिक्का",       "ಪನೀರ್ ಟಿಕ್ಕಾ",      "પનીર ટિક્કા",      "Paneer Tikka",        320, 110, True,  True,  ["pnr tikka","panir tikka"],       "Soft cottage cheese cubes marinated in spices, grilled in tandoor"),
        ("Hara Bhara Kabab",    "हरा भरा कबाब",      "हरा भरा कबाब",      "ಹರಾ ಭರಾ ಕಬಾಬ್",     "હરા ભરા કબાબ",     "Hara Bhara Kabab",    220, 70,  True,  False, ["hara bhara","green kebab"],      "Spinach & pea patties with green chutney"),
        ("Veg Seekh Kabab",     "वेज सीख कबाब",      "व्हेज सीख कबाब",    "ವೆಜ್ ಸೀಖ್ ಕಬಾಬ್",   "વેજ સીખ કબાબ",     "Veg Seekh Kabab",     260, 90,  True,  False, ["seekh kabab veg"],               "Spiced mixed vegetable kabab on skewers"),
        ("Chicken Tikka",       "चिकन टिक्का",       "चिकन टिक्का",       "ಚಿಕನ್ ಟಿಕ್ಕಾ",      "ચિકન ટિક્કા",      "Chicken Tikka",       380, 130, False, True,  ["chicken tikka","chkn tikka"],    "Juicy chicken pieces marinated overnight, tandoor smoked"),
        ("Tandoori Chicken",    "तंदूरी चिकन",       "तंदूरी चिकन",       "ತಂದೂರಿ ಚಿಕನ್",     "તંદૂરી ચિકન",      "Tandoori Chicken",    450, 160, False, True,  ["tandoori","half chicken"],       "Half chicken marinated in yogurt and spices"),
        ("Mutton Seekh Kabab",  "मटन सीख कबाब",      "मटण सीख कबाब",      "ಮಟನ್ ಸೀಖ್ ಕಬಾಬ್",   "મટન સીખ કબાબ",     "Mutton Seekh Kabab",  420, 155, False, False, ["mutton seekh","mutton kabab"],   "Minced mutton on skewers, cooked in tandoor"),
        ("Fish Amritsari",      "फिश अमृतसरी",       "फिश अमृतसरी",       "ಫಿಶ್ ಅಮೃತಸರಿ",      "ફિશ અમૃતસરી",      "Fish Amritsari",      350, 120, False, False, ["fish pakora","amritsari fish"], "Crispy batter fried fish with Amritsari spices"),
        ("Onion Bhajia",        "प्याज भजिया",       "कांदा भजी",         "ಈರುಳ್ಳಿ ಭಜಿ",       "ડુંગળી ભજિયા",     "Pyaaz Bhajiya",       120, 35,  True,  False, ["bhajia","onion pakora"],         "Crispy onion fritters with mint chutney"),
        ("Dahi Ke Sholey",      "दही के शोले",       "दही के शोले",       "ಮೊಸರು ಶೋಲೆ",        "દહીં ના શોલે",     "Dahi Ke Sholey",      280, 95,  True,  False, ["dahi sholey"],                   "Fried cottage cheese with yogurt filling"),
        ("Chicken Malai Tikka", "चिकन मलाई टिक्का",  "चिकन मलाई टिक्का",  "ಚಿಕನ್ ಮಲಾಯ್ ಟಿಕ್ಕಾ","ચિકન મલાઈ ટિક્કા", "Chicken Malai Tikka", 400, 140, False, False, ["malai tikka","creamy tikka"],   "Tender chicken in cream and cheese marinade"),
    ],
    "Soups": [
        ("Tomato Soup",              "टमाटर सूप",         "टोमॅटो सूप",        "ಟೊಮೆಟೊ ಸೂಪ್",      "ટમેટા સૂપ",        "Tamatar Soup",        140, 40,  True,  False, ["tomato","tamatar soup"],         "Classic creamy tomato soup with croutons"),
        ("Sweet Corn Soup",          "स्वीट कॉर्न सूप",   "स्वीट कॉर्न सूप",   "ಸ್ವೀಟ್ ಕಾರ್ನ್ ಸೂಪ್","સ્વીટ કોર્ન સૂપ",  "Sweet Corn Soup",     160, 50,  True,  True,  ["corn soup","sweet corn"],       "Light broth with sweet corn and vegetables"),
        ("Hot & Sour Soup",          "हॉट एंड सॉर सूप",   "हॉट अँड सॉर सूप",   "ಹಾಟ್ ಅಂಡ್ ಸಾರ್ ಸೂಪ್","હોટ એન્ડ સોર સૂપ","Hot aur Sour Soup",   170, 55,  True,  False, ["hot sour"],                    "Tangy spicy soup with vegetables"),
        ("Chicken Shorba",           "चिकन शोरबा",        "चिकन शोरबा",        "ಚಿಕನ್ ಶೋರ್ಬಾ",     "ચિકન શોરબા",       "Chicken Shorba",      200, 65,  False, False, ["shorba","chicken soup"],         "Fragrant Indian-style chicken soup"),
        ("Lentil Soup (Dal Shorba)", "दाल शोरबा",         "डाळ शोरबा",         "ದಾಲ್ ಶೋರ್ಬಾ",      "દાળ શોરબા",        "Dal Shorba",          150, 45,  True,  False, ["dal shorba","lentil soup"],     "Spiced lentil broth with tadka"),
    ],
    "Roti & Naan": [
        ("Butter Naan",    "बटर नान",       "बटर नान",       "ಬಟರ್ ನಾನ್",    "બટર નાન",     "Butter Naan",     60,  18, True, True,  ["naan","butter naan","nan"],          "Soft leavened bread with butter, baked in tandoor"),
        ("Garlic Naan",    "गार्लिक नान",   "गार्लिक नान",   "ಗಾರ್ಲಿಕ್ ನಾನ್","ગાર્લિક નાન", "Garlic Naan",     70,  22, True, True,  ["garlic naan","garlic nan"],          "Naan topped with garlic and coriander"),
        ("Tandoori Roti",  "तंदूरी रोटी",   "तंदूरी रोटी",   "ತಂದೂರಿ ರೋಟಿ",  "તંદૂરી રોટી", "Tandoori Roti",   40,  12, True, False, ["roti","tandoori roti"],              "Whole wheat bread baked in tandoor"),
        ("Missi Roti",     "मिस्सी रोटी",   "मिस्सी रोटी",   "ಮಿಸ್ಸಿ ರೋಟಿ",  "મિસ્સી રોટી", "Missi Roti",      50,  15, True, False, ["missi roti"],                        "Besan spiced flatbread"),
        ("Laccha Paratha", "लच्छा पराठा",   "लच्छा पराठा",   "ಲಚ್ಛಾ ಪರಾಠ",   "લચ્છા પરાઠા", "Laccha Paratha",  70,  25, True, False, ["laccha paratha","layered paratha"], "Flaky layered whole wheat paratha"),
        ("Peshwari Naan",  "पेशवारी नान",   "पेशवारी नान",   "ಪೇಶ್ವಾರಿ ನಾನ್","પેશવારી નાન", "Peshwari Naan",   90,  30, True, False, ["peshwari","stuffed naan"],           "Naan stuffed with almonds, coconut and raisins"),
        ("Kulcha",         "कुलचा",         "कुलचा",         "ಕುಲ್ಚಾ",       "કુલચા",       "Kulcha",          65,  20, True, False, ["kulcha","amritsari kulcha"],         "Soft leavened bread with onion stuffing"),
        ("Roomali Roti",   "रूमाली रोटी",   "रूमाली रोटी",   "ರೂಮಾಲಿ ರೋಟಿ",  "રૂમાલી રોટી", "Roomali Roti",    55,  18, True, False, ["roomali","rumaali roti"],            "Paper thin large flatbread"),
    ],
    "Main Course": [
        ("Paneer Butter Masala","पनीर बटर मसाला",   "पनीर बटर मसाला",   "ಪನೀರ್ ಬಟರ್ ಮಸಾಲ",  "પનીર બટર મસાલા",  "Paneer Butter Masala",360, 120, True,  True,  ["paneer butter","pbm","butter paneer"], "Rich tomato-butter gravy with paneer cubes"),
        ("Dal Makhani",         "दाल मखनी",          "डाळ मखणी",          "ದಾಲ್ ಮಖನಿ",        "દાળ મખણી",         "Dal Makhani",         280, 85,  True,  True,  ["dal makhani","makhani dal"],    "Black lentils slow-cooked overnight in butter and cream"),
        ("Palak Paneer",        "पालक पनीर",         "पालक पनीर",         "ಪಾಲಕ್ ಪನೀರ್",      "પાલક પનીર",        "Palak Paneer",        320, 105, True,  True,  ["palak paneer","spinach paneer"], "Cottage cheese in creamy spinach gravy"),
        ("Shahi Paneer",        "शाही पनीर",         "शाही पनीर",         "ಶಾಹಿ ಪನೀರ್",       "શાહી પનીર",        "Shahi Paneer",        380, 130, True,  False, ["shahi paneer","royal paneer"],  "Paneer in rich cashew and cream sauce"),
        ("Chole Bhature",       "छोले भटूरे",        "छोले भटुरे",        "ಛೋಲೆ ಭಟೂರೆ",       "છોલે ભટુરે",       "Chole Bhature",       220, 70,  True,  True,  ["chole","chhole bhature"],       "Spiced chickpeas served with fried bread"),
        ("Kadai Paneer",        "कड़ाई पनीर",        "कढई पनीर",          "ಕಡಾಯಿ ಪನೀರ್",      "કઢાઈ પનીર",        "Kadai Paneer",        340, 115, True,  False, ["kadai paneer","karahi paneer"], "Paneer cooked with bell peppers in kadai masala"),
        ("Matar Paneer",        "मटर पनीर",          "मटार पनीर",         "ಮಟರ್ ಪನೀರ್",       "મટર પનીર",         "Matar Paneer",        300, 100, True,  False, ["matar paneer","peas paneer"],   "Paneer and green peas in onion-tomato gravy"),
        ("Aloo Gobi",           "आलू गोभी",          "बटाटा फ्लॉवर",      "ಆಲೂ ಗೋಬಿ",         "બટાકા ફ્લાવર",     "Aloo Gobhi",          220, 65,  True,  False, ["aloo gobi","potato cauliflower"], "Potato and cauliflower dry sabzi with spices"),
        ("Butter Chicken",      "बटर चिकन",          "बटर चिकन",          "ಬಟರ್ ಚಿಕನ್",       "બટર ચિકન",         "Butter Chicken",      420, 145, False, True,  ["butter chicken","murgh makhani","makhani chicken"], "Tandoor chicken in creamy tomato butter sauce"),
        ("Chicken Curry",       "चिकन करी",          "चिकन करी",          "ಚಿಕನ್ ಕರಿ",        "ચિકન કરી",         "Chicken Curry",       380, 130, False, False, ["chicken curry","desi chicken"],  "Home-style chicken curry with onion gravy"),
        ("Mutton Rogan Josh",   "मटन रोगन जोश",      "मटण रोगन जोश",      "ಮಟನ್ ರೋಗನ್ ಜೋಶ್",  "મટન રોગન જોશ",    "Mutton Rogan Josh",   520, 185, False, True,  ["rogan josh","mutton curry"],    "Slow-cooked mutton in Kashmiri aromatic spices"),
        ("Lamb Saag",           "लैम्ब साग",          "लँब साग",            "ಲ್ಯಾಂಬ್ ಸಾಗ್",     "લેમ્બ સાગ",         "Lamb Saag",           490, 170, False, False, ["lamb saag","mutton saag"],      "Tender lamb pieces in spiced spinach gravy"),
        ("Fish Curry",          "फिश करी",           "फिश करी",           "ಫಿಶ್ ಕರಿ",         "ફિશ કરી",          "Fish Curry",          440, 155, False, False, ["fish curry","machhi curry"],    "Bengali-style fish cooked in mustard gravy"),
        ("Prawn Masala",        "प्रॉन मसाला",       "प्रॉन मसाला",       "ಪ್ರಾನ್ ಮಸಾಲ",      "પ્રોન મસાલા",      "Prawn Masala",        520, 185, False, False, ["prawn masala","jhinga masala"], "Tiger prawns in spicy onion-tomato masala"),
        ("Dal Tadka",           "दाल तड़का",          "डाळ तडका",           "ದಾಲ್ ತಡ್ಕಾ",       "દાળ તડકા",          "Dal Tadka",           200, 60,  True,  False, ["dal tadka","yellow dal"],       "Yellow lentils tempered with ghee and spices"),
        ("Mix Veg",             "मिक्स वेज",          "मिक्स भाज्या",      "ಮಿಕ್ಸ್ ವೆಜ್",      "મિક્સ વેજ",         "Mix Veg",             260, 80,  True,  False, ["mix veg","mixed vegetables"],   "Seasonal vegetables in rich gravy"),
        ("Methi Malai Matar",   "मेथी मलाई मटर",     "मेथी मलई मटार",     "ಮೆಥಿ ಮಲಾಯ್ ಮಟರ್",  "મેથી મલાઈ મટર",    "Methi Malai Matar",   300, 95,  True,  False, ["methi malai","fenugreek peas"], "Fenugreek and peas in creamy sauce"),
        ("Navratan Korma",      "नवरतन कोरमा",       "नवरतन कोरमा",       "ನವರತ್ನ ಕೋರ್ಮಾ",    "નવરત્ન કોરમા",     "Navratan Korma",      340, 110, True,  False, ["navratan","nine jewel curry"],  "Nine vegetables in royal cream sauce"),
    ],
    "Rice & Biryani": [
        ("Chicken Biryani", "चिकन बिरयानी",   "चिकन बिर्याणी",   "ಚಿಕನ್ ಬಿರಿಯಾನಿ",   "ચિકન બિરયાની",   "Chicken Biryani", 420, 150, False, True,  ["chicken biryani","biryani"],    "Fragrant basmati rice layered with spiced chicken"),
        ("Mutton Biryani",  "मटन बिरयानी",    "मटण बिर्याणी",    "ಮಟನ್ ಬಿರಿಯಾನಿ",    "મટન બિરયાની",    "Mutton Biryani",  520, 190, False, True,  ["mutton biryani"],               "Slow-cooked basmati rice with tender mutton"),
        ("Veg Biryani",     "वेज बिरयानी",    "व्हेज बिर्याणी",  "ವೆಜ್ ಬಿರಿಯಾನಿ",    "વેજ બિરયાની",    "Veg Biryani",     320, 105, True,  False, ["veg biryani","vegetable biryani"], "Aromatic basmati with seasonal vegetables"),
        ("Paneer Biryani",  "पनीर बिरयानी",   "पनीर बिर्याणी",   "ಪನೀರ್ ಬಿರಿಯಾನಿ",   "પનીર બિરયાની",   "Paneer Biryani",  380, 130, True,  False, ["paneer biryani"],               "Biryani with paneer and saffron"),
        ("Prawn Biryani",   "प्रॉन बिरयानी",  "प्रॉन बिर्याणी",  "ಪ್ರಾನ್ ಬಿರಿಯಾನಿ",  "પ્રોન બિરયાની",  "Prawn Biryani",   480, 170, False, False, ["prawn biryani","jhinga biryani"], "Biryani with tiger prawns"),
        ("Jeera Rice",      "जीरा राइस",      "जिरे भात",        "ಜೀರಾ ರೈಸ್",        "જીરા રાઈસ",      "Jeera Rice",      150, 45,  True,  False, ["jeera rice","cumin rice"],      "Basmati rice tempered with cumin"),
        ("Steamed Rice",    "सादा चावल",       "वाफवलेले भात",    "ಬೇಯಿಸಿದ ಅನ್ನ",     "સાદા ભાત",        "Sada Chawal",     100, 30,  True,  False, ["plain rice","steamed rice","chawal"], "Plain boiled basmati rice"),
        ("Fried Rice",      "फ्राइड राइस",    "फ्राइड राइस",    "ಫ್ರೈಡ್ ರೈಸ್",      "ફ્રાઈડ રાઈસ",    "Fried Rice",      200, 65,  True,  False, ["fried rice","chinese rice"],    "Wok-tossed rice with vegetables"),
        ("Pulao",           "पुलाव",           "पुलाव",           "ಪುಲಾವ್",           "પુલાવ",           "Pulao",           220, 70,  True,  False, ["pulao","vegetable pulao"],      "Basmati rice cooked with whole spices and vegetables"),
    ],
    "Desserts": [
        ("Gulab Jamun",   "गुलाब जामुन",      "गुलाब जामुन",      "ಗುಲಾಬ್ ಜಾಮೂನ್",    "ગુલાબ જાંબુ",      "Gulab Jamun",    120, 38, True, True,  ["gulab jamun","gj"],             "Soft milk solid balls soaked in rose syrup"),
        ("Rasgulla",      "रसगुल्ला",          "रसगुल्ला",          "ರಸಗುಲ್ಲಾ",         "રસગુલ્લા",         "Rasgulla",       110, 35, True, False, ["rasgulla","rasagolla"],         "Spongy cottage cheese balls in light syrup"),
        ("Kheer",         "खीर",               "खीर",               "ಖೀರ್",             "ખીર",               "Kheer",          130, 42, True, False, ["kheer","rice pudding"],         "Creamy rice pudding with cardamom and nuts"),
        ("Gajar Ka Halwa","गाजर का हलवा",      "गाजर हलवा",        "ಗಜ್ಜರಿ ಹಲ್ವಾ",     "ગાજર નો હલવો",    "Gajar Ka Halwa", 160, 55, True, True,  ["gajar halwa","carrot halwa"],   "Slow-cooked carrot dessert with ghee and nuts"),
        ("Kulfi",         "कुल्फी",            "कुल्फी",            "ಕುಲ್ಫಿ",           "કુલ્ફી",            "Kulfi",          150, 50, True, False, ["kulfi","indian ice cream"],     "Dense traditional Indian ice cream"),
        ("Phirni",        "फिरनी",             "फिरनी",             "ಫಿರ್ನಿ",           "ફિરની",             "Phirni",         140, 45, True, False, ["phirni","rice kheer"],          "Ground rice cooked in milk, served chilled"),
        ("Jalebi",        "जलेबी",             "जिलबी",             "ಜಿಲೇಬಿ",           "જલેબી",             "Jalebi",         100, 30, True, False, ["jalebi"],                      "Crispy spiral sweets soaked in saffron syrup"),
        ("Shahi Tukda",   "शाही टुकड़ा",       "शाही तुकडा",        "ಶಾಹಿ ತುಕ್ಡಾ",      "શાહી ટુકડા",       "Shahi Tukda",    170, 58, True, False, ["shahi tukda","bread halwa"],    "Fried bread pudding with rabdi and silver leaf"),
        ("Mango Kulfi",   "मैंगो कुल्फी",     "आंबा कुल्फी",      "ಮಾವಿನ ಕುಲ್ಫಿ",     "કેરી કુલ્ફી",      "Mango Kulfi",    180, 62, True, False, ["mango kulfi","aam kulfi"],      "Mango flavored Indian ice cream"),
        ("Rasmalai",      "रसमलाई",            "रसमलाई",            "ರಸಮಲಾಯ್",          "રસમલાઈ",           "Rasmalai",       150, 52, True, True,  ["rasmalai"],                    "Cheese patties in sweetened saffron milk"),
    ],
    "Beverages": [
        ("Masala Chai",     "मसाला चाय",       "मसाला चहा",       "ಮಸಾಲ ಚಹಾ",       "મસાલા ચા",       "Masala Chai",      60,  18, True, True,  ["chai","masala tea","tea"],      "Spiced Indian milk tea"),
        ("Lassi (Sweet)",   "मीठी लस्सी",     "गोड लस्सी",       "ಸಿಹಿ ಲಸ್ಸಿ",     "મીઠી લસ્સી",     "Meethi Lassi",    120,  38, True, True,  ["lassi","sweet lassi"],         "Sweet chilled yogurt drink"),
        ("Mango Lassi",     "मैंगो लस्सी",    "आंबा लस्सी",      "ಮಾವಿನ ಲಸ್ಸಿ",    "કેરી લસ્સી",     "Mango Lassi",     150,  50, True, False, ["mango lassi"],                 "Yogurt blended with fresh Alphonso mango"),
        ("Rose Sharbat",    "गुलाब शरबत",      "गुलाब सरबत",      "ಗುಲಾಬಿ ಶರಬತ್",   "ગુલાબ શરબત",     "Gulab Sharbat",   100,  30, True, False, ["rose sharbat","sharbat"],      "Chilled rose flavored drink"),
        ("Nimbu Pani",      "नींबू पानी",      "लिंबू पाणी",      "ನಿಂಬೆ ಪಾನಿ",     "લીંબુ પાણી",     "Nimbu Pani",       80,  22, True, False, ["nimbu pani","lemonade"],       "Fresh lime water with black salt"),
        ("Jaljeera",        "जलजीरा",          "जलजीरा",          "ಜಲ್ಜೀರಾ",         "જલજીરા",         "Jaljeera",         90,  28, True, False, ["jaljeera"],                    "Cumin-flavored tangy drink"),
        ("Thandai",         "ठंडाई",           "थंडाई",            "ಠಂಡಾಯ್",          "ઠંડાઈ",           "Thandai",         140,  45, True, False, ["thandai"],                     "Cold milk with nuts and saffron"),
        ("Chaas",           "छाछ",             "ताक",              "ಮಜ್ಜಿಗೆ",         "છાશ",             "Chaas",            70,  20, True, False, ["chaas","buttermilk"],          "Spiced buttermilk"),
        ("Cold Coffee",     "कोल्ड कॉफी",     "कोल्ड कॉफी",      "ಕೋಲ್ಡ್ ಕಾಫಿ",    "કોલ્ડ કોફી",     "Cold Coffee",     130,  42, True, False, ["cold coffee"],                 "Blended iced coffee with milk"),
        ("Fresh Lime Soda", "लाइम सोडा",       "लाइम सोडा",       "ಲೈಮ್ ಸೋಡಾ",       "લાઈમ સોડા",      "Lime Soda",        90,  25, True, False, ["lime soda","lemon soda"],      "Fresh lime with chilled soda"),
    ],
    "Salads & Raita": [
        ("Boondi Raita",   "बूंदी रायता",     "बुंदी रायता",     "ಬೂಂದಿ ರೈತಾ",     "બૂંદી રાયતું",    "Boondi Raita",    100, 30, True, False, ["boondi raita","raita"],        "Yogurt with boondi, cumin and mint"),
        ("Cucumber Raita", "खीरा रायता",      "काकडी रायता",     "ಸೌತೆಕಾಯಿ ರೈತಾ",  "કાકડી રાયતું",    "Kheera Raita",     90, 28, True, False, ["cucumber raita"],              "Yogurt with cucumber and spices"),
        ("Onion Salad",    "प्याज सलाद",      "कांदा सॅलड",      "ಈರುಳ್ಳಿ ಸಲಾಡ್",  "ડુંગળી સલાડ",     "Pyaaz Salad",      60, 15, True, False, ["onion salad","pyaz salad"],    "Sliced onions with lemon and chilli"),
        ("Green Salad",    "हरी सलाद",        "हिरवी सॅलड",      "ಹಸಿರು ಸಲಾಡ್",    "લીલું સલાડ",      "Hari Salad",       80, 22, True, False, ["green salad","fresh salad"],   "Mixed garden vegetables with dressing"),
        ("Kachumber",      "कचुंबर",           "कोशिंबीर",        "ಕಚುಂಬರ್",        "કચુંબર",          "Kachumber",        90, 25, True, False, ["kachumber","chopped salad"],   "Chopped onion tomato cucumber salad"),
        ("Fruit Raita",    "फ्रूट रायता",     "फळ रायता",        "ಹಣ್ಣಿನ ರೈತಾ",    "ફ્રૂટ રાયતું",    "Fruit Raita",     120, 38, True, False, ["fruit raita"],                 "Yogurt with fresh seasonal fruits"),
    ],
}

# ══════════════════════════════════════════════════════════════════
#  R2 CATEGORIES & MENU ITEMS  (Dragon Wok — Chinese / Indo-Chinese)
# ══════════════════════════════════════════════════════════════════

R2_CATEGORIES = {
    "Soups":          ("सूप",              "सूप",              "ಸೂಪ್",            "સૂપ",            "Soup",               1),
    "Dim Sum":        ("डिम सम",           "डिम सम",           "ಡಿಮ್ ಸಮ್",        "ડિમ સમ",         "Dim Sum",            2),
    "Starters":       ("स्टार्टर",        "स्टार्टर",        "ಸ್ಟಾರ್ಟರ್",       "સ્ટાર્ટર",       "Starter",            3),
    "Main Course":    ("मुख्य व्यंजन",    "मुख्य पदार्थ",    "ಮುಖ್ಯ ಊಟ",        "મુખ્ય વાનગી",    "Mukhya Vyanjan",     4),
    "Rice & Noodles": ("चावल और नूडल्स",   "भात आणि नूडल्स",  "ಅನ್ನ ಮತ್ತು ನೂಡಲ್ಸ್","ભાત અને નૂડલ્સ","Chawal aur Noodles", 5),
    "Desserts":       ("मिठाई",            "गोड पदार्थ",      "ಸಿಹಿ ತಿನಿಸು",     "મીઠાઈ",          "Mithai",             6),
    "Beverages":      ("पेय पदार्थ",       "पेये",             "ಪಾನೀಯ",           "પીણાં",          "Pey Padarth",        7),
}

R2_ITEMS = {
    "Soups": [
        ("Hot & Sour Soup",  "हॉट एंड सॉर सूप",    "हॉट अँड सॉर सूप",    "ಹಾಟ್ ಅಂಡ್ ಸಾರ್ ಸೂಪ್","હોટ એન્ડ સોર સૂપ","Hot and Sour Soup",  170, 55,  True,  False, ["hot sour soup"],               "Classic Chinese hot and sour broth"),
        ("Sweet Corn Soup",  "स्वीट कॉर्न सूप",    "स्वीट कॉर्न सूप",    "ಸ್ವೀಟ್ ಕಾರ್ನ್ ಸೂಪ್","સ્વીટ કોર્ન સૂપ", "Sweet Corn Soup",   160, 50,  False, True,  ["corn soup"],                   "Silky sweet corn broth with egg drop"),
        ("Tom Yum Soup",     "टॉम यम सूप",          "टॉम यम सूप",          "ಟಾಮ್ ಯಮ್ ಸೂಪ್",     "ટોમ યમ સૂપ",       "Tom Yum Soup",      200, 65,  False, False, ["tom yum"],                     "Thai-inspired spicy prawn and mushroom soup"),
        ("Wonton Soup",      "वॉन्टन सूप",          "वॉन्टन सूप",          "ವಾಂಟನ್ ಸೂಪ್",      "વૉન્ટન સૂપ",       "Wonton Soup",       190, 62,  False, False, ["wonton","dumpling soup"],       "Pork wontons in clear broth"),
        ("Manchow Soup",     "मनचाऊ सूप",           "मनचाऊ सूप",           "ಮಂಚೋ ಸೂಪ್",        "મનચાઉ સૂપ",        "Manchow Soup",      180, 58,  True,  False, ["manchow"],                     "Crispy noodle topped spicy soup"),
    ],
    "Dim Sum": [
        ("Steamed Veg Dim Sum",     "स्टीम्ड वेज डिम सम",     "वाफवलेले व्हेज डिम सम", "ಸ್ಟೀಮ್ಡ್ ವೆಜ್ ಡಿಮ್ ಸಮ್","સ્ટીમ્ડ વેજ ડિમ સમ",   "Steamed Veg Dim Sum",    200, 65, True,  True,  ["veg dim sum","veg momo"],          "Steamed dumplings with vegetable filling"),
        ("Steamed Chicken Dim Sum", "स्टीम्ड चिकन डिम सम",    "वाफवलेले चिकन डिम सम",  "ಸ್ಟೀಮ್ಡ್ ಚಿಕನ್ ಡಿಮ್ ಸಮ್","સ્ટીમ્ડ ચિકન ડિમ સમ", "Steamed Chicken Dim Sum", 240, 80, False, True,  ["chicken dim sum","chicken momo"],   "Steamed dumplings with minced chicken"),
        ("Pan-Fried Pork Bao",      "पैन-फ्राइड पोर्क बाओ",   "पॅन-फ्राइड पोर्क बाओ",  "ಪ್ಯಾನ್ ಫ್ರೈಡ್ ಪೋರ್ಕ್ ಬಾವ್","પેન-ફ્રાઈડ પોર્ક બાઓ","Pan-Fried Pork Bao",   260, 88, False, False, ["pork bao","fried bao"],            "Crispy bottom pork filled steamed bun"),
        ("Crystal Prawn Har Gow",   "क्रिस्टल प्रॉन हर गाऊ",  "क्रिस्टल प्रॉन हर गाऊ", "ಕ್ರಿಸ್ಟಲ್ ಪ್ರಾನ್ ಹಾರ್ ಗೌ","ક્રિસ્ટલ પ્રોન હાર ગાઉ","Crystal Prawn Har Gow", 280, 95, False, False, ["har gow","prawn dumpling"],        "Translucent steamed shrimp dumplings"),
        ("Cheung Fun",              "चंग फन",                  "चंग फन",                 "ಚಂಗ್ ಫನ್",             "ચંગ ફન",                "Cheung Fun",            220, 72, True,  False, ["cheung fun","rice rolls"],         "Silky rice noodle rolls with soy sauce"),
        ("Sesame Prawn Toast",      "तिल प्रॉन टोस्ट",        "तीळ प्रॉन टोस्ट",       "ಎಳ್ಳು ಪ್ರಾನ್ ಟೋಸ್ಟ್", "તલ પ્રોન ટોસ્ટ",       "Til Prawn Toast",       250, 85, False, False, ["prawn toast"],                     "Crispy toasted bread with prawn paste"),
    ],
    "Starters": [
        ("Spring Rolls",         "स्प्रिंग रोल",           "स्प्रिंग रोल",          "ಸ್ಪ್ರಿಂಗ್ ರೋಲ್",       "સ્પ્રિંગ રોલ",        "Spring Roll",          180, 58,  True,  True,  ["spring roll","veg spring roll"], "Crispy fried rolls with vegetable filling"),
        ("Crispy Chilli Chicken","क्रिस्पी चिली चिकन",     "क्रिस्पी चिली चिकन",    "ಕ್ರಿಸ್ಪಿ ಚಿಲ್ಲಿ ಚಿಕನ್","ક્રિસ્પી ચિલી ચિકન",  "Crispy Chilli Chicken", 320, 110, False, True,  ["chilli chicken","crispy chicken"], "Tossed chicken in Indo-Chinese chilli sauce"),
        ("Chicken Lollipop",     "चिकन लॉलीपॉप",           "चिकन लॉलीपॉप",          "ಚಿಕನ್ ಲಾಲಿಪಾಪ್",       "ચિકન લોલીપોપ",        "Chicken Lollipop",     340, 115, False, True,  ["chicken lollipop","lollipop"],   "Frenched chicken wings in spicy glaze"),
        ("Honey Chilli Potato",  "हनी चिली पोटैटो",        "हनी चिली पोटॅटो",       "ಹನಿ ಚಿಲ್ಲಿ ಪೊಟ್ಯಾಟೊ", "હની ચિલી પોટેટો",     "Honey Chilli Potato",  220, 70,  True,  True,  ["honey chilli potato","hcp"],    "Crispy potato fingers in sweet chilli sauce"),
        ("Prawn Tempura",        "प्रॉन टेम्पुरा",        "प्रॉन टेम्पुरा",       "ಪ್ರಾನ್ ಟೆಂಪುರಾ",      "પ્રોન ટેમ્પુરા",      "Prawn Tempura",        360, 125, False, False, ["prawn tempura","tempura"],       "Japanese-style battered fried prawns"),
        ("Tofu Manchurian",      "टोफू मंचूरियन",          "टोफू मंचुरियन",         "ಟೋಫು ಮಂಚೂರಿಯನ್",      "ટોફુ મંચુરિયન",       "Tofu Manchurian",      240, 78,  True,  False, ["tofu manchurian"],               "Crispy tofu balls in Manchurian sauce"),
        ("Chilli Paneer",        "चिली पनीर",              "चिली पनीर",             "ಚಿಲ್ಲಿ ಪನೀರ್",        "ચિલી પનીર",            "Chilli Paneer",        300, 100, True,  False, ["chilli paneer"],                "Cottage cheese tossed in spicy Chinese sauce"),
    ],
    "Main Course": [
        ("Kung Pao Chicken",            "कुंग पाओ चिकन",             "कुंग पाओ चिकन",            "ಕುಂಗ್ ಪಾವ್ ಚಿಕನ್",         "કુંગ પાઓ ચિકન",            "Kung Pao Chicken",           380, 130, False, True,  ["kung pao","kungpao chicken"],   "Diced chicken with peanuts in spicy sauce"),
        ("Sweet & Sour Chicken",        "स्वीट एंड सॉर चिकन",       "स्वीट अँड सॉर चिकन",       "ಸ್ವೀಟ್ ಅಂಡ್ ಸಾರ್ ಚಿಕನ್",  "સ્વીટ એન્ડ સોર ચિકન",      "Sweet and Sour Chicken",     360, 122, False, False, ["sweet sour chicken","sweet and sour"], "Battered chicken in tangy sweet-sour sauce"),
        ("Chicken in Black Bean Sauce", "ब्लैक बीन सॉस चिकन",       "ब्लॅक बीन सॉस चिकन",       "ಬ್ಲ್ಯಾಕ್ ಬೀನ್ ಸಾಸ್ ಚಿಕನ್","બ્લેક બીન સોસ ચિકન",        "Black Bean Sauce Chicken",   370, 125, False, False, ["black bean chicken"],          "Wok-fried chicken with black bean paste"),
        ("Beef with Broccoli",          "बीफ विद ब्रोकली",           "बीफ विथ ब्रोकोली",         "ಬೀಫ್ ವಿತ್ ಬ್ರೊಕೊಲಿ",      "બીફ વિથ બ્રોકલી",          "Beef with Broccoli",         420, 150, False, False, ["beef broccoli"],               "Tender beef slices with broccoli in oyster sauce"),
        ("Mapo Tofu",                   "मापो टोफू",                 "मापो टोफू",                 "ಮಾಪೊ ಟೋಫು",               "માપો ટોફુ",                  "Mapo Tofu",                  280, 92,  True,  False, ["mapo tofu"],                   "Silken tofu in spicy fermented black bean sauce"),
        ("Mongolian Beef",              "मंगोलियन बीफ",              "मंगोलियन बीफ",              "ಮಂಗೋಲಿಯನ್ ಬೀಫ್",          "મંગોલિયન બીફ",              "Mongolian Beef",             430, 155, False, True,  ["mongolian beef"],              "Caramelized beef with scallions in hoisin sauce"),
        ("Szechuan Prawn",              "सेज़वान प्रॉन",             "सेझवान प्रॉन",              "ಸೆಜ್ವಾನ್ ಪ್ರಾನ್",         "સેઝવાન પ્રોન",              "Schezwan Prawn",             460, 165, False, False, ["szechuan prawn","sichuan prawn"], "Wok prawns in fiery Szechuan peppercorn sauce"),
        ("Mixed Vegetable Stir Fry",    "मिक्स वेजिटेबल स्टर फ्राई","मिक्स भाज्या स्टर फ्राय",  "ಮಿಕ್ಸ್ ವೆಜಿಟೆಬಲ್ ಸ್ಟರ್ ಫ್ರೈ","મિક્સ વેજિટેબલ સ્ટર ફ્રાય","Mix Vegetable Stir Fry",    260, 82,  True,  False, ["stir fry veg","vegetable stir fry"], "Crunchy seasonal veggies in oyster sauce"),
        ("General Tso's Chicken",       "जनरल त्सो चिकन",           "जनरल त्सो चिकन",           "ಜನರಲ್ ಸೋಸ್ ಚಿಕನ್",        "જનરલ ત્સો ચિકન",           "General Tso Chicken",        390, 135, False, False, ["general tso"],               "Crispy chicken in tangy, slightly sweet sauce"),
        ("Chilli Garlic Prawns",        "चिली गार्लिक प्रॉन्स",     "चिली गार्लिक प्रॉन्स",    "ಚಿಲ್ಲಿ ಗಾರ್ಲಿಕ್ ಪ್ರಾನ್ಸ್","ચિલી ગાર્લિક પ્રોન્સ",     "Chilli Garlic Prawns",       450, 160, False, False, ["chilli garlic prawn"],        "Wok-tossed prawns with fresh garlic and chilli"),
    ],
    "Rice & Noodles": [
        ("Yang Chow Fried Rice","यांग चाऊ फ्राइड राइस","यांग चाऊ फ्राइड राइस","ಯಾಂಗ್ ಚೌ ಫ್ರೈಡ್ ರೈಸ್","યાંગ ચાઉ ફ્રાઈડ રાઈસ","Yang Chow Fried Rice", 260, 85,  True,  True,  ["yangchow fried rice","yang chow"], "Classic egg fried rice with vegetables"),
        ("Chicken Fried Rice",  "चिकन फ्राइड राइस",   "चिकन फ्राइड राइस",   "ಚಿಕನ್ ಫ್ರೈಡ್ ರೈಸ್",  "ચિકન ફ્રાઈડ રાઈસ",  "Chicken Fried Rice",  290, 98,  False, True,  ["chicken fried rice"],           "Wok-fried rice with chicken and egg"),
        ("Prawn Fried Rice",    "प्रॉन फ्राइड राइस",  "प्रॉन फ्राइड राइस",  "ಪ್ರಾನ್ ಫ್ರೈಡ್ ರೈಸ್", "પ્રોન ફ્રાઈડ રાઈસ", "Prawn Fried Rice",    320, 110, False, False, ["prawn fried rice"],             "Rice stir-fried with tiger prawns"),
        ("Singaporean Noodles", "सिंगापुरी नूडल्स",    "सिंगापुरी नूडल्स",    "ಸಿಂಗಾಪುರಿ ನೂಡಲ್ಸ್", "સિંગાપુરી નૂડલ્સ",  "Singaporean Noodles",  280, 92,  False, False, ["singapore noodles","rice noodles"], "Thin rice noodles with curry powder and prawns"),
        ("Chicken Chow Mein",   "चिकन चाऊ मीन",       "चिकन चाऊ मीन",       "ಚಿಕನ್ ಚೌ ಮೀನ್",     "ચિકન ચાઉ મીન",      "Chicken Chow Mein",   300, 100, False, True,  ["chow mein","chicken noodles"],  "Stir-fried egg noodles with chicken"),
        ("Veg Hakka Noodles",   "वेज हक्का नूडल्स",   "व्हेज हक्का नूडल्स", "ವೆಜ್ ಹಕ್ಕಾ ನೂಡಲ್ಸ್","વેજ હક્કા નૂડલ્સ",  "Veg Hakka Noodles",   240, 78,  True,  True,  ["hakka noodles","veg noodles"],  "Boiled noodles tossed with vegetables"),
        ("Pad Thai",            "पैड थाई",             "पॅड थाई",             "ಪ್ಯಾಡ್ ಥಾಯ್",       "પેડ થાઈ",             "Pad Thai",            310, 105, False, False, ["pad thai"],                    "Thai stir-fried rice noodles with peanuts"),
        ("Steamed Rice",        "स्टीम्ड राइस",       "वाफवलेले भात",        "ಬೇಯಿಸಿದ ಅನ್ನ",      "સ્ટીમ્ડ રાઈસ",      "Steamed Rice",        100, 30,  True,  False, ["plain rice","steamed rice"],   "Plain boiled jasmine rice"),
    ],
    "Desserts": [
        ("Mango Pudding",  "मैंगो पुडिंग",     "आंबा पुडिंग",      "ಮಾವಿನ ಪುಡ್ಡಿಂಗ್",  "કેરી પુડિંગ",      "Mango Pudding",   150, 50, True,  True,  ["mango pudding"],              "Silky mango-flavored pudding"),
        ("Egg Tart",        "एग टार्ट",         "एग टार्ट",         "ಎಗ್ ಟಾರ್ಟ್",       "એગ ટાર્ટ",         "Egg Tart",        120, 38, False, False, ["egg tart","dan tat"],         "Flaky pastry shell with silky egg custard"),
        ("Sesame Ball",     "तिल के लड्डू",     "तिळाचे लाडू",      "ಎಳ್ಳು ಉಂಡೆ",       "તલ ના લાડુ",       "Til Ke Laddu",    110, 35, True,  False, ["sesame ball","jian dui"],      "Crispy glutinous rice ball with lotus paste"),
        ("Ice Cream",       "आइसक्रीम",         "आइस्क्रीम",        "ಐಸ್ ಕ್ರೀಮ್",       "આઈસ્ક્રીમ",        "Ice Cream",       130, 42, True,  False, ["ice cream","vanilla ice cream"], "Two scoops vanilla or chocolate"),
        ("Banana Fritter",  "केले का पकौड़ा",   "केळ्याचे पकोडे",   "ಬಾಳೆಹಣ್ಣಿನ ಪಕೋಡ", "કેળાના ભજિયા",    "Kele Ka Pakoda",  140, 45, True,  False, ["banana fritter","goreng pisang"], "Crispy battered fried banana with honey"),
    ],
    "Beverages": [
        ("Jasmine Green Tea",  "जैस्मिन ग्रीन टी",       "जैस्मिन ग्रीन टी",      "ಜಾಸ್ಮಿನ್ ಗ್ರೀನ್ ಟೀ",    "જૅસ્મિન ગ્રીન ટી",      "Jasmine Green Tea",   80,  22, True,  False, ["green tea","jasmine tea"],    "Floral fragrant jasmine green tea"),
        ("Oolong Tea",         "ऊलोंग चाय",               "ऊलोंग चहा",              "ಊಲಾಂಗ್ ಟೀ",             "ઊલોંગ ચા",                "Oolong Chai",         90,  28, True,  False, ["oolong"],                     "Semi-oxidized traditional Chinese tea"),
        ("Lychee Juice",       "लीची जूस",                 "लीची ज्यूस",             "ಲೀಚಿ ಜ್ಯೂಸ್",           "લીચી જ્યુસ",              "Lychee Juice",       120,  38, True,  True,  ["lychee juice","litchi juice"], "Fresh chilled lychee drink"),
        ("Mango Smoothie",     "मैंगो स्मूदी",             "आंबा स्मूदी",            "ಮಾವಿನ ಸ್ಮೂಥಿ",          "કેરી સ્મૂધી",             "Mango Smoothie",     150,  50, True,  False, ["mango smoothie"],             "Blended fresh mango with yogurt"),
        ("Chinese Cold Beer",  "चाइनीज़ कोल्ड बीयर",      "चायनीज कोल्ड बिअर",     "ಚೈನೀಸ್ ಕೋಲ್ಡ್ ಬಿಯರ್",  "ચાઈનીઝ કોલ્ડ બીયર",      "Chinese Cold Beer",  160,  55, True,  False, ["beer","cold beer"],            "Chilled Kingfisher or Tsingtao"),
    ],
}

# ══════════════════════════════════════════════════════════════════
#  INGREDIENTS
# ══════════════════════════════════════════════════════════════════
# (name, unit, current_stock, reorder_level, cost_per_unit)

R1_INGREDIENTS = [
    ("Chicken",         "kg",  50.0, 10.0, 280.00),
    ("Mutton",          "kg",  30.0, 5.0,  520.00),
    ("Fish (Rohu)",     "kg",  20.0, 4.0,  180.00),
    ("Tiger Prawns",    "kg",  15.0, 3.0,  650.00),
    ("Paneer",          "kg",  40.0, 8.0,  280.00),
    ("Yogurt (Dahi)",   "kg",  25.0, 5.0,  60.00),
    ("Onion",           "kg",  30.0, 5.0,  35.00),
    ("Tomato",          "kg",  25.0, 5.0,  40.00),
    ("Garlic Paste",    "kg",  10.0, 2.0,  120.00),
    ("Ginger Paste",    "kg",  10.0, 2.0,  110.00),
    ("Butter",          "kg",  15.0, 3.0,  450.00),
    ("Cream",           "L",   12.0, 2.0,  120.00),
    ("Ghee",            "kg",  10.0, 2.0,  600.00),
    ("Basmati Rice",    "kg",  50.0, 10.0, 85.00),
    ("Whole Wheat Flour","kg", 30.0, 5.0,  42.00),
    ("Maida (APF)",     "kg",  20.0, 4.0,  38.00),
    ("Cashew Nuts",     "kg",   5.0, 1.0,  850.00),
    ("Almonds",         "kg",   5.0, 1.0,  950.00),
    ("Saffron",         "g",  200.0, 50.0, 5.50),
    ("Cardamom",        "g",  500.0, 100.0, 0.55),
    ("Cumin Seeds",     "g",  800.0, 150.0, 0.18),
    ("Turmeric",        "g",  1000.0, 200.0, 0.12),
    ("Red Chilli Powder","g", 1000.0, 200.0, 0.16),
    ("Garam Masala",    "g",  800.0, 150.0, 0.22),
    ("Spinach",         "kg",  20.0, 4.0,  40.00),
    ("Green Peas",      "kg",  15.0, 3.0,  60.00),
    ("Chickpeas",       "kg",  15.0, 3.0,  80.00),
    ("Black Lentils",   "kg",  20.0, 4.0,  90.00),
    ("Yellow Lentils",  "kg",  20.0, 4.0,  75.00),
    ("Carrot",          "kg",  15.0, 3.0,  35.00),
    ("Milk",            "L",   30.0, 5.0,  55.00),
    ("Sugar",           "kg",  20.0, 4.0,  45.00),
    ("Oil",             "L",   25.0, 5.0,  130.00),
    ("Lemon",           "kg",  10.0, 2.0,  60.00),
    ("Coriander Leaves","kg",   5.0, 1.0,  80.00),
    ("Mint Leaves",     "kg",   4.0, 1.0,  90.00),
    ("Green Chilli",    "kg",   5.0, 1.0,  70.00),
    ("Cauliflower",     "kg",  15.0, 3.0,  35.00),
    ("Potato",          "kg",  25.0, 5.0,  25.00),
    ("Capsicum",        "kg",  10.0, 2.0,  60.00),
    ("Rose Water",      "L",    5.0, 1.0,  180.00),
    ("Condensed Milk",  "kg",  10.0, 2.0,  160.00),
    ("Suji (Semolina)", "kg",  10.0, 2.0,  45.00),
    ("Besan (Gram Flour)","kg", 10.0, 2.0, 55.00),
    ("Soda Water",      "L",   20.0, 4.0,  15.00),
    ("Tea Leaves",      "kg",   5.0, 1.0,  350.00),
    ("Coffee Powder",   "kg",   3.0, 0.5,  650.00),
    ("Mango Pulp",      "kg",  15.0, 3.0,  90.00),
    ("Charcoal",        "kg",  20.0, 4.0,  30.00),
]

R2_INGREDIENTS = [
    ("Chicken (boneless)", "kg", 40.0, 8.0,  280.00),
    ("Pork",               "kg", 25.0, 5.0,  350.00),
    ("Beef",               "kg", 20.0, 4.0,  450.00),
    ("Tiger Prawns",       "kg", 15.0, 3.0,  650.00),
    ("Tofu",               "kg", 20.0, 4.0,  120.00),
    ("Paneer",             "kg", 15.0, 3.0,  280.00),
    ("Jasmine Rice",       "kg", 40.0, 8.0,  75.00),
    ("Egg Noodles",        "kg", 15.0, 3.0,  90.00),
    ("Rice Noodles",       "kg", 10.0, 2.0,  85.00),
    ("Egg",                "pcs",200,  40,   8.00),
    ("Soy Sauce",          "L",  10.0, 2.0,  130.00),
    ("Oyster Sauce",       "L",   8.0, 1.5,  280.00),
    ("Sesame Oil",         "L",   5.0, 1.0,  450.00),
    ("Hoisin Sauce",       "L",   5.0, 1.0,  320.00),
    ("Corn Starch",        "kg", 10.0, 2.0,  80.00),
    ("Ginger",             "kg",  8.0, 1.5,  110.00),
    ("Garlic",             "kg",  8.0, 1.5,  120.00),
    ("Spring Onion",       "kg",  8.0, 1.5,  60.00),
    ("Broccoli",           "kg", 12.0, 2.5,  80.00),
    ("Bok Choy",           "kg", 10.0, 2.0,  70.00),
    ("Red Bell Pepper",    "kg", 10.0, 2.0,  90.00),
    ("Bean Sprouts",       "kg",  8.0, 1.5,  60.00),
    ("Mushrooms (Shiitake)","kg", 8.0, 1.5,  280.00),
    ("Cabbage",            "kg", 12.0, 2.0,  35.00),
    ("Carrot",             "kg", 10.0, 2.0,  35.00),
    ("Potato",             "kg", 15.0, 3.0,  25.00),
    ("Peanuts",            "kg",  5.0, 1.0,  180.00),
    ("Chilli Bean Paste",  "kg",  5.0, 1.0,  280.00),
    ("Black Bean Paste",   "kg",  5.0, 1.0,  250.00),
    ("Sweet & Sour Sauce", "L",   8.0, 1.5,  180.00),
    ("Honey",              "kg",  5.0, 1.0,  350.00),
    ("Sesame Seeds",       "kg",  5.0, 1.0,  220.00),
    ("Wonton Wrappers",    "pcs", 500, 100,  1.20),
    ("Dumpling Wrappers",  "pcs", 500, 100,  0.90),
    ("Lychee (canned)",    "kg",  8.0, 1.5,  180.00),
    ("Mango",              "kg",  8.0, 1.5,  120.00),
    ("Jasmine Tea Leaves", "kg",  3.0, 0.5,  900.00),
    ("Glutinous Rice Flour","kg", 5.0, 1.0,  75.00),
    ("Oil",                "L",  20.0, 4.0,  130.00),
    ("Sugar",              "kg", 10.0, 2.0,  45.00),
    ("Vinegar",            "L",   5.0, 1.0,  80.00),
    ("Szechuan Pepper",    "g",  400.0, 80.0, 0.90),
]

# ══════════════════════════════════════════════════════════════════
#  RECIPES  —  item_name → [(ingredient_name, qty_per_serving)]
# ══════════════════════════════════════════════════════════════════

R1_RECIPES = {
    "Paneer Tikka":         [("Paneer", 200), ("Yogurt (Dahi)", 80), ("Garlic Paste", 15), ("Ginger Paste", 15), ("Oil", 20), ("Red Chilli Powder", 5), ("Garam Masala", 3), ("Lemon", 20)],
    "Hara Bhara Kabab":     [("Spinach", 100), ("Green Peas", 50), ("Potato", 60), ("Besan (Gram Flour)", 30), ("Oil", 20), ("Green Chilli", 5), ("Garam Masala", 3)],
    "Veg Seekh Kabab":      [("Potato", 80), ("Cauliflower", 60), ("Besan (Gram Flour)", 40), ("Onion", 40), ("Oil", 20), ("Garam Masala", 4)],
    "Chicken Tikka":        [("Chicken", 250), ("Yogurt (Dahi)", 80), ("Garlic Paste", 20), ("Ginger Paste", 20), ("Oil", 25), ("Red Chilli Powder", 6), ("Garam Masala", 4), ("Lemon", 20)],
    "Tandoori Chicken":     [("Chicken", 400), ("Yogurt (Dahi)", 120), ("Garlic Paste", 25), ("Ginger Paste", 25), ("Oil", 30), ("Red Chilli Powder", 8), ("Garam Masala", 5)],
    "Mutton Seekh Kabab":   [("Mutton", 220), ("Onion", 60), ("Garlic Paste", 20), ("Ginger Paste", 20), ("Garam Masala", 5), ("Oil", 25)],
    "Fish Amritsari":       [("Fish (Rohu)", 250), ("Besan (Gram Flour)", 60), ("Oil", 300), ("Garlic Paste", 15), ("Lemon", 25), ("Red Chilli Powder", 6)],
    "Onion Bhajia":         [("Onion", 100), ("Besan (Gram Flour)", 60), ("Oil", 200), ("Green Chilli", 8), ("Turmeric", 3)],
    "Dahi Ke Sholey":       [("Paneer", 100), ("Yogurt (Dahi)", 100), ("Besan (Gram Flour)", 40), ("Oil", 150)],
    "Chicken Malai Tikka":  [("Chicken", 250), ("Cream", 80), ("Yogurt (Dahi)", 60), ("Garlic Paste", 15), ("Ginger Paste", 15), ("Oil", 20), ("Cardamom", 4)],
    "Tomato Soup":          [("Tomato", 200), ("Onion", 60), ("Butter", 20), ("Cream", 40), ("Sugar", 10)],
    "Sweet Corn Soup":      [("Green Peas", 80), ("Onion", 40), ("Butter", 15), ("Cream", 30)],
    "Hot & Sour Soup":      [("Tomato", 80), ("Capsicum", 40), ("Onion", 40), ("Oil", 15)],
    "Chicken Shorba":       [("Chicken", 150), ("Onion", 60), ("Tomato", 80), ("Ginger Paste", 10), ("Garlic Paste", 10), ("Garam Masala", 4)],
    "Lentil Soup (Dal Shorba)": [("Yellow Lentils", 80), ("Tomato", 60), ("Onion", 40), ("Butter", 15), ("Garam Masala", 3)],
    "Butter Naan":          [("Maida (APF)", 120), ("Butter", 25), ("Yogurt (Dahi)", 30)],
    "Garlic Naan":          [("Maida (APF)", 120), ("Butter", 20), ("Yogurt (Dahi)", 30), ("Garlic Paste", 10)],
    "Tandoori Roti":        [("Whole Wheat Flour", 100)],
    "Missi Roti":           [("Whole Wheat Flour", 60), ("Besan (Gram Flour)", 40), ("Oil", 15)],
    "Laccha Paratha":       [("Whole Wheat Flour", 100), ("Ghee", 20)],
    "Peshwari Naan":        [("Maida (APF)", 120), ("Almonds", 20), ("Butter", 20)],
    "Kulcha":               [("Maida (APF)", 120), ("Onion", 40), ("Butter", 20)],
    "Roomali Roti":         [("Maida (APF)", 80), ("Whole Wheat Flour", 40)],
    "Paneer Butter Masala": [("Paneer", 200), ("Tomato", 120), ("Onion", 80), ("Butter", 40), ("Cream", 60), ("Cashew Nuts", 25), ("Garlic Paste", 15), ("Ginger Paste", 15), ("Garam Masala", 5)],
    "Dal Makhani":          [("Black Lentils", 120), ("Butter", 40), ("Cream", 50), ("Tomato", 80), ("Garlic Paste", 15), ("Ginger Paste", 10)],
    "Palak Paneer":         [("Spinach", 150), ("Paneer", 180), ("Onion", 60), ("Tomato", 60), ("Butter", 25), ("Cream", 40), ("Garlic Paste", 12)],
    "Shahi Paneer":         [("Paneer", 200), ("Cashew Nuts", 40), ("Cream", 80), ("Tomato", 80), ("Onion", 60), ("Butter", 30), ("Saffron", 0.5)],
    "Chole Bhature":        [("Chickpeas", 150), ("Onion", 80), ("Tomato", 80), ("Oil", 30), ("Garam Masala", 5), ("Maida (APF)", 120)],
    "Kadai Paneer":         [("Paneer", 200), ("Capsicum", 80), ("Tomato", 80), ("Onion", 80), ("Oil", 30), ("Garam Masala", 5)],
    "Matar Paneer":         [("Paneer", 160), ("Green Peas", 80), ("Tomato", 80), ("Onion", 60), ("Oil", 25), ("Garam Masala", 4)],
    "Aloo Gobi":            [("Potato", 120), ("Cauliflower", 150), ("Onion", 60), ("Tomato", 60), ("Oil", 25), ("Turmeric", 4)],
    "Butter Chicken":       [("Chicken", 280), ("Butter", 50), ("Cream", 80), ("Tomato", 120), ("Onion", 80), ("Cashew Nuts", 30), ("Garlic Paste", 20), ("Garam Masala", 6)],
    "Chicken Curry":        [("Chicken", 280), ("Onion", 100), ("Tomato", 100), ("Oil", 35), ("Garlic Paste", 20), ("Ginger Paste", 15), ("Garam Masala", 6)],
    "Mutton Rogan Josh":    [("Mutton", 280), ("Onion", 100), ("Yogurt (Dahi)", 80), ("Oil", 35), ("Garlic Paste", 20), ("Ginger Paste", 20), ("Garam Masala", 8)],
    "Lamb Saag":            [("Mutton", 260), ("Spinach", 200), ("Onion", 80), ("Tomato", 60), ("Oil", 30), ("Garlic Paste", 15)],
    "Fish Curry":           [("Fish (Rohu)", 280), ("Onion", 80), ("Tomato", 80), ("Oil", 30), ("Turmeric", 5), ("Red Chilli Powder", 6)],
    "Prawn Masala":         [("Tiger Prawns", 280), ("Onion", 100), ("Tomato", 100), ("Oil", 35), ("Garlic Paste", 20), ("Garam Masala", 6)],
    "Dal Tadka":            [("Yellow Lentils", 100), ("Onion", 60), ("Tomato", 60), ("Ghee", 20), ("Cumin Seeds", 5)],
    "Mix Veg":              [("Potato", 60), ("Cauliflower", 60), ("Green Peas", 60), ("Carrot", 60), ("Oil", 25), ("Onion", 60), ("Tomato", 60)],
    "Methi Malai Matar":    [("Green Peas", 100), ("Cream", 60), ("Onion", 60), ("Butter", 25)],
    "Navratan Korma":       [("Paneer", 80), ("Potato", 60), ("Carrot", 60), ("Green Peas", 60), ("Cashew Nuts", 30), ("Cream", 60), ("Butter", 25)],
    "Chicken Biryani":      [("Chicken", 300), ("Basmati Rice", 200), ("Onion", 80), ("Yogurt (Dahi)", 80), ("Saffron", 0.5), ("Ghee", 30), ("Garam Masala", 6)],
    "Mutton Biryani":       [("Mutton", 280), ("Basmati Rice", 200), ("Onion", 80), ("Yogurt (Dahi)", 80), ("Saffron", 0.5), ("Ghee", 35), ("Garam Masala", 7)],
    "Veg Biryani":          [("Basmati Rice", 200), ("Potato", 60), ("Carrot", 60), ("Green Peas", 60), ("Saffron", 0.5), ("Ghee", 25), ("Onion", 60)],
    "Paneer Biryani":       [("Basmati Rice", 200), ("Paneer", 120), ("Saffron", 0.5), ("Ghee", 25), ("Onion", 60), ("Yogurt (Dahi)", 60)],
    "Prawn Biryani":        [("Tiger Prawns", 250), ("Basmati Rice", 200), ("Saffron", 0.5), ("Ghee", 30), ("Onion", 80)],
    "Jeera Rice":           [("Basmati Rice", 180), ("Cumin Seeds", 8), ("Ghee", 15)],
    "Steamed Rice":         [("Basmati Rice", 160)],
    "Fried Rice":           [("Basmati Rice", 160), ("Oil", 20), ("Carrot", 40), ("Green Peas", 40)],
    "Pulao":                [("Basmati Rice", 180), ("Onion", 40), ("Carrot", 40), ("Green Peas", 40), ("Ghee", 20)],
    "Gulab Jamun":          [("Milk", 100), ("Maida (APF)", 50), ("Sugar", 80), ("Cardamom", 2), ("Rose Water", 10)],
    "Rasgulla":             [("Milk", 200), ("Sugar", 100)],
    "Kheer":                [("Basmati Rice", 40), ("Milk", 300), ("Sugar", 60), ("Cardamom", 2), ("Almonds", 10), ("Saffron", 0.3)],
    "Gajar Ka Halwa":       [("Carrot", 250), ("Milk", 200), ("Sugar", 80), ("Ghee", 30), ("Cardamom", 2), ("Almonds", 15)],
    "Kulfi":                [("Milk", 250), ("Sugar", 60), ("Cardamom", 2), ("Almonds", 15), ("Saffron", 0.3)],
    "Phirni":               [("Basmati Rice", 30), ("Milk", 280), ("Sugar", 65), ("Cardamom", 2), ("Saffron", 0.3)],
    "Jalebi":               [("Maida (APF)", 80), ("Sugar", 100), ("Oil", 200), ("Saffron", 0.2)],
    "Shahi Tukda":          [("Maida (APF)", 80), ("Milk", 200), ("Sugar", 80), ("Ghee", 40), ("Almonds", 15), ("Saffron", 0.3)],
    "Mango Kulfi":          [("Milk", 200), ("Mango Pulp", 100), ("Sugar", 55), ("Cardamom", 2)],
    "Rasmalai":             [("Milk", 300), ("Sugar", 80), ("Saffron", 0.4), ("Cardamom", 2), ("Almonds", 10)],
    "Masala Chai":          [("Tea Leaves", 5), ("Milk", 120), ("Sugar", 15), ("Ginger Paste", 5), ("Cardamom", 2)],
    "Lassi (Sweet)":        [("Yogurt (Dahi)", 200), ("Sugar", 30), ("Rose Water", 10)],
    "Mango Lassi":          [("Yogurt (Dahi)", 180), ("Mango Pulp", 80), ("Sugar", 25)],
    "Rose Sharbat":         [("Sugar", 40), ("Rose Water", 30)],
    "Nimbu Pani":           [("Lemon", 40), ("Sugar", 25)],
    "Jaljeera":             [("Lemon", 30), ("Cumin Seeds", 5), ("Sugar", 20)],
    "Thandai":              [("Milk", 200), ("Sugar", 40), ("Almonds", 20), ("Cardamom", 3), ("Saffron", 0.3)],
    "Chaas":                [("Yogurt (Dahi)", 150)],
    "Cold Coffee":          [("Milk", 180), ("Coffee Powder", 15), ("Sugar", 30)],
    "Fresh Lime Soda":      [("Lemon", 35), ("Soda Water", 200), ("Sugar", 20)],
    "Boondi Raita":         [("Yogurt (Dahi)", 150), ("Besan (Gram Flour)", 30), ("Oil", 30), ("Cumin Seeds", 3)],
    "Cucumber Raita":       [("Yogurt (Dahi)", 150)],
    "Onion Salad":          [("Onion", 80), ("Lemon", 15)],
    "Green Salad":          [("Carrot", 40), ("Lemon", 15), ("Coriander Leaves", 10)],
    "Kachumber":            [("Onion", 60), ("Tomato", 60), ("Lemon", 15), ("Coriander Leaves", 10)],
    "Fruit Raita":          [("Yogurt (Dahi)", 150), ("Sugar", 20), ("Cardamom", 1)],
}

R2_RECIPES = {
    "Hot & Sour Soup":        [("Mushrooms (Shiitake)", 60), ("Cabbage", 50), ("Corn Starch", 15), ("Vinegar", 10), ("Soy Sauce", 15), ("Chilli Bean Paste", 10)],
    "Sweet Corn Soup":        [("Corn Starch", 20), ("Egg", 1), ("Soy Sauce", 10), ("Spring Onion", 20)],
    "Tom Yum Soup":           [("Tiger Prawns", 100), ("Mushrooms (Shiitake)", 50), ("Lychee (canned)", 30), ("Spring Onion", 20), ("Chilli Bean Paste", 15)],
    "Wonton Soup":            [("Pork", 80), ("Wonton Wrappers", 6), ("Soy Sauce", 15), ("Spring Onion", 20), ("Ginger", 10)],
    "Manchow Soup":           [("Cabbage", 60), ("Carrot", 40), ("Soy Sauce", 15), ("Corn Starch", 15), ("Egg Noodles", 30)],
    "Steamed Veg Dim Sum":    [("Cabbage", 60), ("Carrot", 40), ("Mushrooms (Shiitake)", 40), ("Dumpling Wrappers", 5), ("Soy Sauce", 10)],
    "Steamed Chicken Dim Sum":[("Chicken (boneless)", 80), ("Dumpling Wrappers", 5), ("Soy Sauce", 10), ("Ginger", 10), ("Spring Onion", 15)],
    "Pan-Fried Pork Bao":     [("Pork", 80), ("Wonton Wrappers", 4), ("Soy Sauce", 12), ("Ginger", 10), ("Oil", 20)],
    "Crystal Prawn Har Gow":  [("Tiger Prawns", 80), ("Dumpling Wrappers", 5), ("Ginger", 8), ("Sesame Oil", 8)],
    "Cheung Fun":             [("Rice Noodles", 120), ("Soy Sauce", 15), ("Sesame Oil", 10), ("Spring Onion", 20)],
    "Sesame Prawn Toast":     [("Tiger Prawns", 80), ("Sesame Seeds", 20), ("Oil", 100), ("Spring Onion", 15)],
    "Spring Rolls":           [("Cabbage", 80), ("Carrot", 50), ("Bean Sprouts", 50), ("Egg Noodles", 30), ("Oil", 150)],
    "Crispy Chilli Chicken":  [("Chicken (boneless)", 200), ("Corn Starch", 30), ("Oil", 200), ("Chilli Bean Paste", 20), ("Garlic", 15), ("Spring Onion", 20)],
    "Chicken Lollipop":       [("Chicken (boneless)", 200), ("Corn Starch", 30), ("Oil", 180), ("Chilli Bean Paste", 20), ("Garlic", 15)],
    "Honey Chilli Potato":    [("Potato", 200), ("Honey", 30), ("Chilli Bean Paste", 15), ("Oil", 200), ("Garlic", 10), ("Spring Onion", 20)],
    "Prawn Tempura":          [("Tiger Prawns", 200), ("Corn Starch", 40), ("Oil", 250), ("Ginger", 10)],
    "Tofu Manchurian":        [("Tofu", 200), ("Corn Starch", 30), ("Oil", 150), ("Soy Sauce", 20), ("Chilli Bean Paste", 15), ("Spring Onion", 20)],
    "Chilli Paneer":          [("Paneer", 200), ("Corn Starch", 30), ("Oil", 150), ("Chilli Bean Paste", 20), ("Soy Sauce", 15), ("Red Bell Pepper", 60)],
    "Kung Pao Chicken":       [("Chicken (boneless)", 220), ("Peanuts", 40), ("Chilli Bean Paste", 20), ("Soy Sauce", 20), ("Oil", 30), ("Garlic", 15), ("Ginger", 10)],
    "Sweet & Sour Chicken":   [("Chicken (boneless)", 220), ("Sweet & Sour Sauce", 60), ("Corn Starch", 30), ("Oil", 180), ("Red Bell Pepper", 50)],
    "Chicken in Black Bean Sauce": [("Chicken (boneless)", 220), ("Black Bean Paste", 40), ("Garlic", 15), ("Ginger", 10), ("Oil", 25), ("Spring Onion", 20)],
    "Beef with Broccoli":     [("Beef", 220), ("Broccoli", 150), ("Oyster Sauce", 30), ("Soy Sauce", 15), ("Oil", 25), ("Garlic", 15)],
    "Mapo Tofu":              [("Tofu", 250), ("Pork", 60), ("Black Bean Paste", 30), ("Chilli Bean Paste", 25), ("Oil", 25), ("Szechuan Pepper", 2)],
    "Mongolian Beef":         [("Beef", 230), ("Hoisin Sauce", 40), ("Soy Sauce", 20), ("Spring Onion", 40), ("Oil", 30), ("Sugar", 15)],
    "Szechuan Prawn":         [("Tiger Prawns", 230), ("Szechuan Pepper", 3), ("Chilli Bean Paste", 25), ("Oil", 30), ("Garlic", 15), ("Ginger", 10)],
    "Mixed Vegetable Stir Fry":[("Broccoli", 80), ("Bok Choy", 80), ("Carrot", 60), ("Mushrooms (Shiitake)", 60), ("Oyster Sauce", 25), ("Oil", 25)],
    "General Tso's Chicken":  [("Chicken (boneless)", 220), ("Corn Starch", 30), ("Hoisin Sauce", 30), ("Oil", 200), ("Chilli Bean Paste", 15)],
    "Chilli Garlic Prawns":   [("Tiger Prawns", 230), ("Garlic", 25), ("Chilli Bean Paste", 20), ("Oil", 25), ("Spring Onion", 20)],
    "Yang Chow Fried Rice":   [("Jasmine Rice", 200), ("Egg", 2), ("Spring Onion", 30), ("Soy Sauce", 15), ("Oil", 25)],
    "Chicken Fried Rice":     [("Jasmine Rice", 200), ("Chicken (boneless)", 100), ("Egg", 1), ("Soy Sauce", 15), ("Oil", 25), ("Spring Onion", 20)],
    "Prawn Fried Rice":       [("Jasmine Rice", 200), ("Tiger Prawns", 100), ("Egg", 1), ("Soy Sauce", 15), ("Oil", 25), ("Spring Onion", 20)],
    "Singaporean Noodles":    [("Rice Noodles", 150), ("Tiger Prawns", 80), ("Egg", 1), ("Soy Sauce", 15), ("Oil", 25), ("Cabbage", 50)],
    "Chicken Chow Mein":      [("Egg Noodles", 150), ("Chicken (boneless)", 100), ("Soy Sauce", 15), ("Oil", 25), ("Bean Sprouts", 50), ("Spring Onion", 25)],
    "Veg Hakka Noodles":      [("Egg Noodles", 150), ("Cabbage", 60), ("Carrot", 50), ("Bean Sprouts", 50), ("Soy Sauce", 15), ("Oil", 25)],
    "Pad Thai":               [("Rice Noodles", 150), ("Tiger Prawns", 80), ("Egg", 1), ("Peanuts", 25), ("Bean Sprouts", 50), ("Oil", 25), ("Sugar", 15)],
    "Steamed Rice":           [("Jasmine Rice", 160)],
    "Mango Pudding":          [("Mango", 150), ("Sugar", 50), ("Corn Starch", 15)],
    "Egg Tart":               [("Egg", 2), ("Sugar", 40), ("Corn Starch", 20)],
    "Sesame Ball":            [("Glutinous Rice Flour", 80), ("Sesame Seeds", 30), ("Sugar", 40), ("Oil", 150)],
    "Ice Cream":              [("Sugar", 40)],
    "Banana Fritter":         [("Corn Starch", 50), ("Sugar", 30), ("Honey", 20), ("Oil", 150)],
    "Jasmine Green Tea":      [("Jasmine Tea Leaves", 4)],
    "Oolong Tea":             [("Jasmine Tea Leaves", 5)],
    "Lychee Juice":           [("Lychee (canned)", 150), ("Sugar", 20)],
    "Mango Smoothie":         [("Mango", 150), ("Sugar", 30)],
    "Chinese Cold Beer":      [],
}

# ═══════════════════════════════════════════════════════════════
#  MAIN SEEDING FUNCTION
# ═══════════════════════════════════════════════════════════════

def run():
    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    print("Running DDL (drop + recreate all tables)...")
    cur.execute(DDL)
    conn.commit()
    print("  ✓ Schema created")

    # ── 1. restaurants ──────────────────────────────────────────
    def insert_restaurant(r):
        cur.execute("""
            INSERT INTO restaurants (name, slug, email, password_hash, phone, address, cuisine_type)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (r["name"], r["slug"], r["email"], h(r["password"]),
              r["phone"], r["address"], r["cuisine_type"]))
        rid = cur.fetchone()[0]
        cur.execute("""
            INSERT INTO restaurant_settings (restaurant_id) VALUES (%s)
        """, (rid,))
        return rid

    r1_id = insert_restaurant(RESTAURANT_1)
    r2_id = insert_restaurant(RESTAURANT_2)
    conn.commit()
    print(f"  ✓ Restaurants created: R1={r1_id} (Spice Craft), R2={r2_id} (Dragon Wok)")

    # ── 2. categories ───────────────────────────────────────────
    def insert_categories(restaurant_id, cat_dict):
        cat_ids = {}
        for name, (name_hi, name_mr, name_kn, name_gu, name_hi_en, order) in cat_dict.items():
            cur.execute("""
                INSERT INTO categories
                    (restaurant_id, name, name_hi, name_mr, name_kn, name_gu, name_hi_en, display_order)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """, (restaurant_id, name, name_hi, name_mr, name_kn, name_gu, name_hi_en, order))
            cat_ids[name] = cur.fetchone()[0]
        return cat_ids

    r1_cats = insert_categories(r1_id, R1_CATEGORIES)
    r2_cats = insert_categories(r2_id, R2_CATEGORIES)
    conn.commit()
    print(f"  ✓ Categories: {len(r1_cats)} for R1, {len(r2_cats)} for R2")

    # ── 3. ingredients ──────────────────────────────────────────
    def insert_ingredients(restaurant_id, ing_list):
        ing_ids = {}
        for name, unit, stock, reorder, cost in ing_list:
            cur.execute("""
                INSERT INTO ingredients
                    (restaurant_id, name, unit, current_stock, reorder_level, cost_per_unit)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
            """, (restaurant_id, name, unit, stock, reorder, cost))
            ing_ids[name] = cur.fetchone()[0]
        return ing_ids

    r1_ings = insert_ingredients(r1_id, R1_INGREDIENTS)
    r2_ings = insert_ingredients(r2_id, R2_INGREDIENTS)
    conn.commit()
    print(f"  ✓ Ingredients: {len(r1_ings)} for R1, {len(r2_ings)} for R2")

    # ── 4. menu items + recipes ─────────────────────────────────
    def insert_menu_items(restaurant_id, cat_ids, items_dict, recipes, ing_ids):
        item_ids = {}
        for cat_name, items in items_dict.items():
            cid = cat_ids.get(cat_name)
            for row in items:
                name, name_hi, name_mr, name_kn, name_gu, name_hi_en, \
                    price, food_cost, is_veg, bestseller, aliases, desc = row
                is_bestseller = bool(bestseller) and random.random() < 0.5
                cur.execute("""
                    INSERT INTO menu_items
                        (restaurant_id, name, name_hi, name_mr, name_kn, name_gu, name_hi_en,
                         description, aliases,
                         category_id, selling_price, food_cost,
                         is_veg, is_available, is_bestseller,
                         modifiers, tags)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s,%s,%s) RETURNING id
                """, (
                    restaurant_id, name, name_hi, name_mr, name_kn, name_gu, name_hi_en,
                    desc, aliases,
                    cid, price, food_cost,
                    is_veg, is_bestseller,
                    json.dumps({"spice_level": ["mild", "medium", "hot"]}),
                    json.dumps(["veg"] if is_veg else ["non-veg"]),
                ))
                item_id = cur.fetchone()[0]
                item_ids[name] = (item_id, price)
                # insert recipe
                recipe = recipes.get(name, [])
                for ing_name, qty in recipe:
                    iid = ing_ids.get(ing_name)
                    if iid:
                        cur.execute("""
                            INSERT INTO menu_item_ingredients
                                (menu_item_id, ingredient_id, quantity_used)
                            VALUES (%s,%s,%s)
                            ON CONFLICT (menu_item_id, ingredient_id) DO NOTHING
                        """, (item_id, iid, qty))
        return item_ids  # {name: (id, price)}

    r1_items = insert_menu_items(r1_id, r1_cats, R1_ITEMS, R1_RECIPES, r1_ings)
    r2_items = insert_menu_items(r2_id, r2_cats, R2_ITEMS, R2_RECIPES, r2_ings)
    conn.commit()
    print(f"  ✓ Menu items: {len(r1_items)} for R1, {len(r2_items)} for R2")

    # ── 5. restaurant tables ─────────────────────────────────────
    def insert_tables(restaurant_id, count=15):
        tbl_ids = []
        sections = ["main"] * 8 + ["patio"] * 4 + ["private"] * 3
        caps     = [2, 4, 4, 4, 6, 6, 8, 4, 4, 2, 4, 4, 6, 8, 4]
        for i in range(count):
            cur.execute("""
                INSERT INTO restaurant_tables
                    (restaurant_id, table_number, capacity, section, status)
                VALUES (%s,%s,%s,%s,'empty') RETURNING id
            """, (restaurant_id, f"T{i+1}", caps[i], sections[i]))
            tbl_ids.append(cur.fetchone()[0])
        return tbl_ids

    r1_tables = insert_tables(r1_id)
    r2_tables = insert_tables(r2_id, 10)
    conn.commit()
    print(f"  ✓ Tables: {len(r1_tables)} for R1, {len(r2_tables)} for R2")

    # ── 6. historical orders (200 per restaurant) ────────────────
    payment_methods = ["cash", "card", "upi"]
    order_types     = ["dine_in", "dine_in", "dine_in", "takeaway", "delivery"]
    guest_names     = ["Rohit Sharma", "Priya Verma", "Amit Gupta", "Sunita Rao",
                       "Kiran Patel", "Deepak Nair", "Anita Joshi", "Vijay Menon",
                       "Pooja Singh", "Rahul Mehta", "Kavita Iyer", "Arjun Reddy",
                       "Meera Nambiar", "Sanjay Tiwari", "Rekha Pillai", "Li Wei",
                       "Chen Fang", "Wang Yu", "Zhang Min", "Liu Jing"]

    def insert_orders(restaurant_id, table_ids, item_map, count=200):
        item_list = list(item_map.items())  # [(name, (id, price)), ...]
        order_counter = 0
        stock_usage = {}  # ingredient_id → total usage (negative)

        # preload recipes: item_id → [(ingredient_id, qty)]
        recipe_map = {}
        cur2 = conn.cursor()
        cur2.execute("""
            SELECT mii.menu_item_id, mii.ingredient_id, mii.quantity_used
            FROM menu_item_ingredients mii
            JOIN menu_items mi ON mi.id = mii.menu_item_id
            WHERE mi.restaurant_id = %s
        """, (restaurant_id,))
        for row in cur2.fetchall():
            recipe_map.setdefault(row[0], []).append((row[1], float(row[2])))
        cur2.close()

        for _ in range(count):
            order_counter += 1
            created = rand_dt(90, 1)
            settled = created + timedelta(minutes=random.randint(20, 90))
            table_id = random.choice(table_ids) if random.random() < 0.75 else None
            otype    = random.choice(order_types)
            pmethod  = random.choice(payment_methods)
            guest_ct = random.randint(1, 6)
            guest_n  = random.choice(guest_names)

            oid_str = f"ORD-{created.strftime('%Y%m%d')}-{uid()}"
            cur.execute("""
                INSERT INTO orders
                    (restaurant_id, order_id, order_number, status, order_type,
                     table_id, source,
                     guest_name, guest_count, payment_method, settled_at,
                     created_at, updated_at)
                VALUES (%s,%s,%s,'confirmed',%s,%s,'manual',%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (restaurant_id, oid_str, f"#{order_counter}",
                  otype, table_id,
                  guest_n, guest_ct, pmethod, settled,
                  created, settled))
            order_pk = cur.fetchone()[0]

            # Add 2–6 random items to the order
            n_items = random.randint(2, 6)
            chosen  = random.choices(item_list, k=n_items)
            total   = Decimal("0.00")
            for iname, (item_id, price) in chosen:
                qty       = random.randint(1, 3)
                unit_p    = Decimal(str(price))
                line_tot  = unit_p * qty
                total    += line_tot
                cur.execute("""
                    INSERT INTO order_items
                        (order_pk, item_id, quantity, unit_price, line_total)
                    VALUES (%s,%s,%s,%s,%s)
                """, (order_pk, item_id, qty, unit_p, line_tot))

                # accumulate stock usage
                for ing_id, ing_qty in recipe_map.get(item_id, []):
                    stock_usage[ing_id] = stock_usage.get(ing_id, 0.0) + ing_qty * qty

            cur.execute("UPDATE orders SET total_amount=%s WHERE id=%s", (total, order_pk))

        # bulk-insert stock usage logs
        if stock_usage:
            for ing_id, total_used in stock_usage.items():
                cur.execute("""
                    INSERT INTO stock_logs
                        (ingredient_id, change_qty, reason, note, created_at)
                    VALUES (%s,%s,'usage','Deducted from historical orders',%s)
                """, (ing_id, -round(total_used, 2), rand_dt(90, 1)))
                # reduce current stock
                cur.execute("""
                    UPDATE ingredients
                    SET current_stock = GREATEST(0, current_stock - %s)
                    WHERE id = %s
                """, (round(total_used, 2), ing_id))

        print(f"    R{restaurant_id}: {count} orders inserted, ingredient stock updated")

    print("Inserting historical orders...")
    insert_orders(r1_id, r1_tables, r1_items, 200)
    conn.commit()
    insert_orders(r2_id, r2_tables, r2_items, 200)
    conn.commit()

    print("\n✅ Database seeded successfully!")
    print(f"   Spice Garden (Indian):  {len(r1_items)} menu items, 200 orders")
    print(f"   Dragon Wok  (Chinese):  {len(r2_items)} menu items, 200 orders")
    print("   All multilingual fields filled: hi, mr, kn, gu, hi_en")
    print("   Credentials: email as above, password = admin123")
    cur.close()
    conn.close()


if __name__ == "__main__":
    run()
