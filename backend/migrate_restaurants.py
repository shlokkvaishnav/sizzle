"""
migrate_restaurants.py
======================
1. Creates the `restaurants` table
2. Adds `restaurant_id` column to categories, menu_items, sale_transactions,
   orders, staff, shifts, combo_suggestions
3. Creates Restaurant 1: "Sizzle Indian Kitchen" (links ALL existing data)
4. Creates Restaurant 2: "Dragon Wok" (Chinese restaurant with its own menu)
5. Generates sample sale_transactions for Dragon Wok
"""
import sys, hashlib, random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")
from sqlalchemy import text
from database import engine, SessionLocal
from models import Restaurant, Category, MenuItem, VSale

def sha256(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

# ═══════════════════════════════
# STEP 1: Create restaurants table
# ═══════════════════════════════
print("── Step 1: Create restaurants table ──")
with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS restaurants (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(200) UNIQUE NOT NULL,
            password_hash VARCHAR(256) NOT NULL,
            phone VARCHAR(20),
            address TEXT,
            cuisine_type VARCHAR(100),
            logo_url VARCHAR(500),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))
    conn.commit()
    print("  ✅ restaurants table ready")

# ═══════════════════════════════
# STEP 2: Add restaurant_id columns
# ═══════════════════════════════
print("\n── Step 2: Add restaurant_id columns ──")
TABLES = ["categories", "menu_items", "sale_transactions", "orders", "staff", "shifts", "combo_suggestions"]

with engine.connect() as conn:
    for table in TABLES:
        try:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN restaurant_id INTEGER REFERENCES restaurants(id)"))
            conn.commit()
            print(f"  ✅ {table}.restaurant_id added")
        except Exception as e:
            conn.rollback()
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print(f"  ⏭️  {table}.restaurant_id already exists")
            else:
                print(f"  ⚠️  {table}: {e}")

# ═══════════════════════════════
# STEP 3: Create restaurants
# ═══════════════════════════════
print("\n── Step 3: Create restaurant accounts ──")
db = SessionLocal()

# Restaurant 1: Sizzle Indian Kitchen
r1 = db.query(Restaurant).filter(Restaurant.slug == "sizzle-indian").first()
if not r1:
    r1 = Restaurant(
        name="Sizzle Indian Kitchen",
        slug="sizzle-indian",
        email="admin@sizzle.in",
        password_hash=sha256("sizzle123"),
        phone="+91 98765 43210",
        address="FC Road, Pune, Maharashtra 411005",
        cuisine_type="Indian Multi-Cuisine",
    )
    db.add(r1)
    db.flush()
    print(f"  ✅ Restaurant 1: {r1.name} (id={r1.id})")
    print(f"     📧 Email: admin@sizzle.in")
    print(f"     🔑 Password: sizzle123")
else:
    print(f"  ⏭️  Restaurant 1 exists (id={r1.id})")

# Restaurant 2: Dragon Wok
r2 = db.query(Restaurant).filter(Restaurant.slug == "dragon-wok").first()
if not r2:
    r2 = Restaurant(
        name="Dragon Wok",
        slug="dragon-wok",
        email="admin@dragonwok.in",
        password_hash=sha256("dragon123"),
        phone="+91 98765 12345",
        address="MG Road, Bangalore, Karnataka 560001",
        cuisine_type="Chinese & Pan-Asian",
    )
    db.add(r2)
    db.flush()
    print(f"  ✅ Restaurant 2: {r2.name} (id={r2.id})")
    print(f"     📧 Email: admin@dragonwok.in")
    print(f"     🔑 Password: dragon123")
else:
    print(f"  ⏭️  Restaurant 2 exists (id={r2.id})")

db.commit()

# ═══════════════════════════════
# STEP 4: Link existing data → Restaurant 1
# ═══════════════════════════════
print("\n── Step 4: Link existing data to Restaurant 1 ──")
with engine.connect() as conn:
    for table in TABLES:
        try:
            result = conn.execute(text(f"UPDATE {table} SET restaurant_id = :rid WHERE restaurant_id IS NULL"), {"rid": r1.id})
            conn.commit()
            print(f"  ✅ {table}: {result.rowcount} rows linked to '{r1.name}'")
        except Exception as e:
            conn.rollback()
            print(f"  ⚠️  {table}: {e}")

# ═══════════════════════════════
# STEP 5: Seed Dragon Wok menu
# ═══════════════════════════════
print("\n── Step 5: Seed Dragon Wok menu ──")

def add_cat(name, name_hi, name_mr, name_kn, name_gu, name_hi_en, order):
    existing = db.query(Category).filter(Category.name == name, Category.restaurant_id == r2.id).first()
    if existing:
        return existing
    cat = Category(
        restaurant_id=r2.id, name=name, name_hi=name_hi, name_mr=name_mr,
        name_kn=name_kn, name_gu=name_gu, name_hi_en=name_hi_en,
        display_order=order, is_active=True,
    )
    db.add(cat)
    db.flush()
    return cat

def add_item(cat_id, name, name_hi, name_mr, name_kn, name_gu, name_hi_en,
             price, cost, aliases="", is_veg=True, is_bestseller=False, tags=None):
    existing = db.query(MenuItem).filter(MenuItem.name == name, MenuItem.restaurant_id == r2.id).first()
    if existing:
        return existing
    item = MenuItem(
        restaurant_id=r2.id, category_id=cat_id,
        name=name, name_hi=name_hi, name_mr=name_mr,
        name_kn=name_kn, name_gu=name_gu, name_hi_en=name_hi_en,
        selling_price=price, food_cost=cost, aliases=aliases,
        is_veg=is_veg, is_available=True, is_bestseller=is_bestseller,
        tags=tags or [],
    )
    db.add(item)
    db.flush()
    return item

# Categories for Dragon Wok
c_appetizers = add_cat("Appetizers", "ऐपेटाइज़र", "ऍपेटायझर", "ಅಪೆಟೈಜರ್ಸ್", "એપેટાઇઝર", "Appetizers", 1)
c_soups = add_cat("Soups", "सूप", "सूप", "ಸೂಪ್", "સૂપ", "Soups", 2)
c_rice_noodles = add_cat("Rice & Noodles", "राइस और नूडल्स", "राइस आणि नूडल्स", "ರೈಸ್ ಮತ್ತು ನೂಡಲ್ಸ್", "રાઈસ અને નૂડલ્સ", "Rice & Noodles", 3)
c_mains = add_cat("Main Course", "मुख्य व्यंजन", "मुख्य पदार्थ", "ಮುಖ್ಯ ಊಟ", "મુખ્ય ભોજન", "Main Course", 4)
c_dim_sum = add_cat("Dim Sum & Dumplings", "डिम सम और मोमो", "डिम सम आणि मोमो", "ಡಿಮ್ ಸಮ್ ಮತ್ತು ಮೋಮೋ", "ડિમ સમ અને મોમો", "Dim Sum & Momos", 5)
c_sizzlers = add_cat("Sizzlers & Platters", "सिज़लर और प्लैटर", "सिझलर आणि प्लॅटर", "ಸಿಜ್ಲರ್ ಮತ್ತು ಪ್ಲಾಟರ್", "સિઝલર અને પ્લેટર", "Sizzlers & Platters", 6)
c_drinks = add_cat("Drinks & Desserts", "ड्रिंक्स और मिठाई", "ड्रिंक्स आणि मिठाई", "ಡ್ರಿಂಕ್ಸ್ ಮತ್ತು ಡೆಸರ್ಟ್", "ડ્રિંક્સ અને મીઠાઈ", "Drinks & Desserts", 7)

# ── APPETIZERS ──
print("  Appetizers...")
add_item(c_appetizers.id, "Crispy Chilli Chicken", "क्रिस्पी चिल्ली चिकन", "क्रिस्पी चिल्ली चिकन", "ಕ್ರಿಸ್ಪಿ ಚಿಲ್ಲಿ ಚಿಕನ್", "ક્રિસ્પી ચિલ્લી ચિકન", "Crispy Chilli Chicken",
         280, 85, "chilli chicken|crispy chicken|dry chilli chicken", is_veg=False, is_bestseller=True, tags=["spicy", "appetizer"])
add_item(c_appetizers.id, "Honey Chilli Potato", "हनी चिल्ली पोटैटो", "हनी चिल्ली पोटॅटो", "ಹನಿ ಚಿಲ್ಲಿ ಪೊಟ್ಯಾಟೊ", "હની ચિલ્લી પોટેટો", "Honey Chilli Potato",
         220, 50, "honey chilli potato|crispy potato|hcp", tags=["sweet-spicy", "appetizer"])
add_item(c_appetizers.id, "Salt & Pepper Tofu", "सॉल्ट एंड पेपर टोफू", "सॉल्ट अँड पेपर टोफू", "ಸಾಲ್ಟ್ ಅಂಡ್ ಪೆಪರ್ ಟೋಫು", "સોલ્ટ એન્ડ પેપર ટોફુ", "Salt & Pepper Tofu",
         200, 45, "salt pepper tofu|tofu fry|crispy tofu", tags=["appetizer"])
add_item(c_appetizers.id, "Dragon Prawns", "ड्रैगन प्रॉन्स", "ड्रॅगन प्रॉन्स", "ಡ್ರ್ಯಾಗನ್ ಪ್ರಾನ್ಸ್", "ડ્રેગન પ્રોન્સ", "Dragon Prawns",
         380, 140, "dragon prawns|spicy prawns|prawn fry", is_veg=False, tags=["seafood", "premium", "appetizer"])
add_item(c_appetizers.id, "Chicken Spring Rolls", "चिकन स्प्रिंग रोल", "चिकन स्प्रिंग रोल", "ಚಿಕನ್ ಸ್ಪ್ರಿಂಗ್ ರೋಲ್", "ચિકન સ્પ્રિંગ રોલ", "Chicken Spring Rolls",
         220, 65, "chicken roll|spring roll chicken", is_veg=False, tags=["appetizer"])
add_item(c_appetizers.id, "Veg Spring Rolls", "वेज स्प्रिंग रोल", "व्हेज स्प्रिंग रोल", "ವೆಜ್ ಸ್ಪ್ರಿಂಗ್ ರೋಲ್", "વેજ સ્પ્રિંગ રોલ", "Veg Spring Rolls",
         180, 40, "veg roll|spring roll veg", tags=["appetizer"])
add_item(c_appetizers.id, "Crispy Corn Pepper Salt", "क्रिस्पी कॉर्न पेपर सॉल्ट", "क्रिस्पी कॉर्न पेपर सॉल्ट", "ಕ್ರಿಸ್ಪಿ ಕಾರ್ನ್ ಪೆಪರ್ ಸಾಲ್ಟ್", "ક્રિસ્પી કોર્ન પેપર સોલ્ટ", "Crispy Corn Pepper Salt",
         200, 45, "corn salt pepper|crispy corn chinese", tags=["appetizer"])
add_item(c_appetizers.id, "Kung Pao Chicken", "कुंग पाओ चिकन", "कुंग पाओ चिकन", "ಕುಂಗ್ ಪಾವ್ ಚಿಕನ್", "કુંગ પાઓ ચિકન", "Kung Pao Chicken",
         300, 95, "kung pao|kung pao chicken|gong bao", is_veg=False, is_bestseller=True, tags=["spicy", "appetizer"])

# ── SOUPS ──
print("  Soups...")
add_item(c_soups.id, "Hot & Sour Veg Soup", "हॉट एंड सॉर सूप", "हॉट अँड सॉर सूप", "ಹಾಟ್ ಅಂಡ್ ಸೌರ್ ಸೂಪ್", "હોટ એન્ડ સાર સૂપ", "Hot & Sour Soup",
         150, 30, "hot sour soup|hot n sour", tags=["soup"])
add_item(c_soups.id, "Wonton Soup", "वॉन्टन सूप", "वॉन्टन सूप", "ವಾಂಟನ್ ಸೂಪ್", "વોન્ટન સૂપ", "Wonton Soup",
         180, 45, "wonton soup|won ton", is_veg=False, tags=["soup"])
add_item(c_soups.id, "Tom Yum Soup", "टॉम यम सूप", "टॉम यम सूप", "ಟಾಮ್ ಯಮ್ ಸೂಪ್", "ટોમ યમ સૂપ", "Tom Yum Soup",
         200, 55, "tom yum|thai soup", is_veg=False, tags=["soup", "thai", "spicy"])
add_item(c_soups.id, "Sweet Corn Chicken Soup", "स्वीट कॉर्न चिकन सूप", "स्वीट कॉर्न चिकन सूप", "ಸ್ವೀಟ್ ಕಾರ್ನ್ ಚಿಕನ್ ಸೂಪ್", "સ્વીટ કોર્ન ચિકન સૂપ", "Sweet Corn Chicken Soup",
         170, 45, "chicken corn soup|corn chicken", is_veg=False, tags=["soup"])
add_item(c_soups.id, "Manchow Veg Soup", "मंचाऊ वेज सूप", "मंचाऊ व्हेज सूप", "ಮಂಚೋ ವೆಜ್ ಸೂಪ್", "મંચાઉ વેજ સૂપ", "Manchow Veg Soup",
         150, 30, "manchow soup|manchow veg", tags=["soup"])

# ── RICE & NOODLES ──
print("  Rice & Noodles...")
add_item(c_rice_noodles.id, "Veg Fried Rice", "वेज फ्राइड राइस", "व्हेज फ्राईड राईस", "ವೆಜ್ ಫ್ರೈಡ್ ರೈಸ್", "વેજ ફ્રાઈડ રાઈસ", "Veg Fried Rice",
         180, 40, "veg fried rice|fried rice", tags=["rice"])
add_item(c_rice_noodles.id, "Chicken Fried Rice", "चिकन फ्राइड राइस", "चिकन फ्राईड राईस", "ಚಿಕನ್ ಫ್ರೈಡ್ ರೈಸ್", "ચિકન ફ્રાઈડ રાઈસ", "Chicken Fried Rice",
         220, 65, "chicken rice|chkn fried rice", is_veg=False, tags=["rice"])
add_item(c_rice_noodles.id, "Schezwan Fried Rice", "शेजवान फ्राइड राइस", "शेझवान फ्राईड राईस", "ಶೆಜ್ವಾನ್ ಫ್ರೈಡ್ ರೈಸ್", "શેઝવાન ફ્રાઈડ રાઈસ", "Schezwan Fried Rice",
         200, 50, "schezwan rice|spicy rice", tags=["rice", "spicy"])
add_item(c_rice_noodles.id, "Thai Basil Rice", "थाई बेसिल राइस", "थाई बेसिल राईस", "ಥಾಯ್ ಬೆಸಿಲ್ ರೈಸ್", "થાઈ બેસિલ રાઈસ", "Thai Basil Rice",
         240, 60, "basil rice|thai rice", tags=["rice", "thai"])
add_item(c_rice_noodles.id, "Veg Hakka Noodles", "वेज हक्का नूडल्स", "व्हेज हक्का नूडल्स", "ವೆಜ್ ಹಕ್ಕಾ ನೂಡಲ್ಸ್", "વેજ હક્કા નૂડલ્સ", "Veg Hakka Noodles",
         180, 40, "veg noodles|hakka noodles|chowmein", tags=["noodles"])
add_item(c_rice_noodles.id, "Chicken Hakka Noodles", "चिकन हक्का नूडल्स", "चिकन हक्का नूडल्स", "ಚಿಕನ್ ಹಕ್ಕಾ ನೂಡಲ್ಸ್", "ચિકન હક્કા નૂડલ્સ", "Chicken Hakka Noodles",
         220, 65, "chicken noodles|chkn noodles", is_veg=False, tags=["noodles"])
add_item(c_rice_noodles.id, "Singapore Noodles", "सिंगापुर नूडल्स", "सिंगापूर नूडल्स", "ಸಿಂಗಪುರ ನೂಡಲ್ಸ್", "સિંગાપુર નૂડલ્સ", "Singapore Noodles",
         250, 70, "singapore noodles|spicy noodles|rice noodles", is_veg=False, tags=["noodles", "premium"])
add_item(c_rice_noodles.id, "Pad Thai Noodles", "पैड थाई नूडल्स", "पॅड थाई नूडल्स", "ಪ್ಯಾಡ್ ಥಾಯ್ ನೂಡಲ್ಸ್", "પેડ થાઈ નૂડલ્સ", "Pad Thai Noodles",
         260, 75, "pad thai|thai noodles", tags=["noodles", "thai"])

# ── MAIN COURSE ──
print("  Main Course...")
add_item(c_mains.id, "Chicken Manchurian Gravy", "चिकन मंचूरियन ग्रेवी", "चिकन मंचुरियन ग्रेव्ही", "ಚಿಕನ್ ಮಂಚೂರಿಯನ್ ಗ್ರೇವಿ", "ચિકન મંચુરિયન ગ્રેવી", "Chicken Manchurian Gravy",
         280, 85, "chicken manchurian|manchurian gravy chicken", is_veg=False, is_bestseller=True, tags=["main"])
add_item(c_mains.id, "Veg Manchurian Gravy", "वेज मंचूरियन ग्रेवी", "व्हेज मंचुरियन ग्रेव्ही", "ವೆಜ್ ಮಂಚೂರಿಯನ್ ಗ್ರೇವಿ", "વેજ મંચુરિયન ગ્રેવી", "Veg Manchurian Gravy",
         220, 50, "veg manchurian gravy|gobi manchurian gravy", tags=["main"])
add_item(c_mains.id, "Chicken in Black Bean Sauce", "चिकन इन ब्लैक बीन सॉस", "चिकन इन ब्लॅक बीन सॉस", "ಚಿಕನ್ ಇನ್ ಬ್ಲ್ಯಾಕ್ ಬೀನ್ ಸಾಸ್", "ચિકન ઇન બ્લેક બીન સોસ", "Chicken Black Bean",
         320, 100, "black bean chicken|black bean sauce", is_veg=False, tags=["main", "premium"])
add_item(c_mains.id, "Mapo Tofu", "मापो टोफू", "मापो टोफू", "ಮಾಪೋ ಟೋಫು", "માપો ટોફુ", "Mapo Tofu",
         240, 55, "mapo tofu|spicy tofu|sichuan tofu", tags=["main", "sichuan", "spicy"])
add_item(c_mains.id, "Thai Green Curry", "थाई ग्रीन करी", "थाई ग्रीन करी", "ಥಾಯ್ ಗ್ರೀನ್ ಕರಿ", "થાઈ ગ્રીન કરી", "Thai Green Curry",
         300, 90, "green curry|thai curry|green curry chicken", is_veg=False, tags=["main", "thai"])
add_item(c_mains.id, "Thai Red Curry", "थाई रेड करी", "थाई रेड करी", "ಥಾಯ್ ರೆಡ್ ಕರಿ", "થાઈ રેડ કરી", "Thai Red Curry",
         300, 90, "red curry|thai red|panang curry", tags=["main", "thai"])
add_item(c_mains.id, "Sweet & Sour Chicken", "स्वीट एंड सॉर चिकन", "स्वीट अँड सॉर चिकन", "ಸ್ವೀಟ್ ಅಂಡ್ ಸೌರ್ ಚಿಕನ್", "સ્વીટ એન્ડ સાર ચિકન", "Sweet & Sour Chicken",
         280, 85, "sweet sour chicken|sweet n sour", is_veg=False, tags=["main"])
add_item(c_mains.id, "Paneer Chilli Gravy", "पनीर चिल्ली ग्रेवी", "पनीर चिल्ली ग्रेव्ही", "ಪನೀರ್ ಚಿಲ್ಲಿ ಗ್ರೇವಿ", "પનીર ચિલ્લી ગ્રેવી", "Paneer Chilli Gravy",
         240, 60, "chilli paneer gravy|paneer chilli", tags=["main", "spicy"])

# ── DIM SUM & DUMPLINGS ──
print("  Dim Sum & Dumplings...")
add_item(c_dim_sum.id, "Chicken Momos (Steamed)", "चिकन मोमो (स्टीम)", "चिकन मोमो (स्टीम)", "ಚಿಕನ್ ಮೋಮೋ (ಸ್ಟೀಮ್)", "ચિકન મોમો (સ્ટીમ)", "Chicken Momos Steamed",
         200, 60, "chicken momo|steamed momo|chkn momo", is_veg=False, is_bestseller=True, tags=["dim-sum"])
add_item(c_dim_sum.id, "Veg Momos (Steamed)", "वेज मोमो (स्टीम)", "व्हेज मोमो (स्टीम)", "ವೆಜ್ ಮೋಮೋ (ಸ್ಟೀಮ್)", "વેજ મોમો (સ્ટીમ)", "Veg Momos Steamed",
         160, 35, "veg momo|steamed veg momo", tags=["dim-sum"])
add_item(c_dim_sum.id, "Chicken Momos (Fried)", "चिकन मोमो (फ्राइड)", "चिकन मोमो (फ्राईड)", "ಚಿಕನ್ ಮೋಮೋ (ಫ್ರೈಡ್)", "ચિકન મોમો (ફ્રાઈડ)", "Chicken Momos Fried",
         220, 65, "fried momo chicken|crispy momo", is_veg=False, tags=["dim-sum"])
add_item(c_dim_sum.id, "Veg Momos (Fried)", "वेज मोमो (फ्राइड)", "व्हेज मोमो (फ्राईड)", "ವೆಜ್ ಮೋಮೋ (ಫ್ರೈಡ್)", "વેજ મોમો (ફ્રાઈડ)", "Veg Momos Fried",
         180, 40, "fried momo veg|crispy veg momo", tags=["dim-sum"])
add_item(c_dim_sum.id, "Prawn Har Gow", "प्रॉन हार गो", "प्रॉन हार गो", "ಪ್ರಾನ್ ಹಾರ್ ಗೊ", "પ્રોન હાર ગો", "Prawn Har Gow",
         350, 130, "har gow|prawn dumpling|crystal dumpling", is_veg=False, tags=["dim-sum", "premium"])
add_item(c_dim_sum.id, "Chicken Sui Mai", "चिकन सुई माई", "चिकन सुई माई", "ಚಿಕನ್ ಸುಯಿ ಮಾಯ್", "ચિકન સુઈ માઈ", "Chicken Sui Mai",
         280, 85, "sui mai|siu mai|shumai chicken", is_veg=False, tags=["dim-sum"])
add_item(c_dim_sum.id, "Tandoori Momos", "तंदूरी मोमो", "तंदूरी मोमो", "ತಂದೂರಿ ಮೋಮೋ", "તંદૂરી મોમો", "Tandoori Momos",
         240, 70, "tandoori momo|grilled momo", is_veg=False, tags=["dim-sum", "fusion"])

# ── SIZZLERS ──
print("  Sizzlers...")
add_item(c_sizzlers.id, "Chicken Sizzler", "चिकन सिज़लर", "चिकन सिझलर", "ಚಿಕನ್ ಸಿಜ್ಲರ್", "ચિકન સિઝલર", "Chicken Sizzler",
         450, 150, "chicken sizzler|sizzler chicken", is_veg=False, is_bestseller=True, tags=["sizzler", "premium"])
add_item(c_sizzlers.id, "Paneer Sizzler", "पनीर सिज़लर", "पनीर सिझलर", "ಪನೀರ್ ಸಿಜ್ಲರ್", "પનીર સિઝલર", "Paneer Sizzler",
         400, 120, "paneer sizzler|veg sizzler", tags=["sizzler", "premium"])
add_item(c_sizzlers.id, "Dragon Platter (Non-Veg)", "ड्रैगन प्लैटर (नॉन-वेज)", "ड्रॅगन प्लॅटर (नॉन-व्हेज)", "ಡ್ರ್ಯಾಗನ್ ಪ್ಲಾಟರ್ (ನಾನ್-ವೆಜ್)", "ડ્રેગન પ્લેટર (નોન-વેજ)", "Dragon Platter Non-Veg",
         550, 200, "dragon platter|non veg platter|mega platter", is_veg=False, tags=["sizzler", "premium", "sharing"])

# ── DRINKS & DESSERTS ──
print("  Drinks & Desserts...")
add_item(c_drinks.id, "Jasmine Tea", "जैस्मिन चाय", "जॅस्मिन चहा", "ಜಾಸ್ಮಿನ್ ಚಹಾ", "જેસ્મિન ચા", "Jasmine Tea",
         120, 20, "jasmine tea|chinese tea|green tea", tags=["drink", "hot"])
add_item(c_drinks.id, "Lychee Iced Tea", "लीची आइस्ड टी", "लीची आईस्ड टी", "ಲೀಚಿ ಐಸ್ಡ್ ಟೀ", "લીચી આઈસ્ડ ટી", "Lychee Iced Tea",
         150, 30, "lychee tea|iced lychee|litchi tea", tags=["drink", "cold"])
add_item(c_drinks.id, "Mango Sticky Rice", "मैंगो स्टिकी राइस", "मँगो स्टिकी राईस", "ಮ್ಯಾಂಗೋ ಸ್ಟಿಕ್ಕಿ ರೈಸ್", "મેંગો સ્ટિકી રાઈસ", "Mango Sticky Rice",
         220, 60, "mango sticky rice|thai dessert|sticky rice mango", tags=["dessert", "thai"])
add_item(c_drinks.id, "Fried Ice Cream", "फ्राइड आइसक्रीम", "फ्राईड आईस्क्रीम", "ಫ್ರೈಡ್ ಐಸ್ ಕ್ರೀಮ್", "ફ્રાઈડ આઈસક્રીમ", "Fried Ice Cream",
         180, 45, "fried ice cream|crispy ice cream", tags=["dessert"])
add_item(c_drinks.id, "Dragon Fruit Smoothie", "ड्रैगन फ्रूट स्मूदी", "ड्रॅगन फ्रूट स्मूदी", "ಡ್ರ್ಯಾಗನ್ ಫ್ರೂಟ್ ಸ್ಮೂತಿ", "ડ્રેગન ફ્રુટ સ્મૂધી", "Dragon Fruit Smoothie",
         200, 50, "dragon fruit|smoothie|pitaya smoothie", tags=["drink", "healthy"])
add_item(c_drinks.id, "Virgin Lychee Mojito", "वर्जिन लीची मोजिटो", "व्हर्जिन लीची मोजिटो", "ವರ್ಜಿನ್ ಲೀಚಿ ಮೊಜಿಟೊ", "વર્જિન લીચી મોજીટો", "Virgin Lychee Mojito",
         200, 45, "lychee mojito|litchi mojito", tags=["drink", "mocktail"])

db.commit()

# ═══════════════════════════════
# STEP 6: Generate sales data for Dragon Wok
# ═══════════════════════════════
print("\n── Step 6: Generate Dragon Wok sales data ──")
dragon_items = db.query(MenuItem).filter(MenuItem.restaurant_id == r2.id).all()

if not db.query(VSale).filter(VSale.restaurant_id == r2.id).first():
    now = datetime.now(timezone.utc)
    order_counter = 9000
    txns = []

    for day_offset in range(60):
        date = now - timedelta(days=day_offset)
        num_orders = random.randint(15, 40)

        for _ in range(num_orders):
            order_counter += 1
            order_id = f"DW-{date.strftime('%Y%m%d')}-{order_counter}"
            items_in_order = random.sample(dragon_items, k=min(random.randint(2, 5), len(dragon_items)))
            order_type = random.choice(["dine_in", "dine_in", "dine_in", "takeaway", "delivery"])

            for item in items_in_order:
                qty = random.randint(1, 3)
                txns.append(VSale(
                    restaurant_id=r2.id,
                    item_id=item.id,
                    order_id=order_id,
                    quantity=qty,
                    unit_price=item.selling_price,
                    total_price=item.selling_price * qty,
                    order_type=order_type,
                    sold_at=date.replace(
                        hour=random.randint(11, 22),
                        minute=random.randint(0, 59),
                    ),
                ))

    db.add_all(txns)
    db.commit()
    print(f"  ✅ Generated {len(txns)} sale transactions for Dragon Wok")
else:
    print("  ⏭️  Dragon Wok sales data already exists")

# Summary
r1_items = db.query(MenuItem).filter(MenuItem.restaurant_id == r1.id).count()
r2_items = db.query(MenuItem).filter(MenuItem.restaurant_id == r2.id).count()
r1_sales = db.query(VSale).filter(VSale.restaurant_id == r1.id).count()
r2_sales = db.query(VSale).filter(VSale.restaurant_id == r2.id).count()

print(f"""
╔══════════════════════════════════════════════════════╗
║              MULTI-RESTAURANT SETUP DONE             ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  🍛 Restaurant 1: Sizzle Indian Kitchen              ║
║     Email: admin@sizzle.in                           ║
║     Pass:  sizzle123                                 ║
║     Items: {r1_items:<5} | Sales: {r1_sales:<6}                    ║
║                                                      ║
║  🐉 Restaurant 2: Dragon Wok                         ║
║     Email: admin@dragonwok.in                        ║
║     Pass:  dragon123                                 ║
║     Items: {r2_items:<5} | Sales: {r2_sales:<6}                    ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
""")

db.close()
