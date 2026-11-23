# ⚡ AURX WEAR - Official Clothing Catalog Website

A modern, high-fashion streetwear catalog website with 1-click WhatsApp ordering and an intuitive admin panel to upload photos and manage inventory.

---

## 🚀 How to Run the Website

### Option 1 (Easiest - 1 Click):
Simply double-click the **`start.bat`** file in this folder. It will start the server and automatically open the website in your browser!

### Option 2 (Via Terminal / PowerShell):
Run:
```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```
Then visit:
- **Customer Storefront:** [http://localhost:8000](http://localhost:8000)
- **Admin Control Panel:** [http://localhost:8000/admin](http://localhost:8000/admin)

---

## 🔐 Admin Panel Details

- **URL:** `http://localhost:8000/admin`
- **Default Password:** `aurx123` *(Aap ise Admin Panel ke "Store Settings" tab se kabhi bhi change kar sakte hain)*

### Admin Panel Features:
1. **Add New Clothes:**
   - Multiple photo uploads with automatic compression for fast loading.
   - Title, Category, Price, and MRP (to show % OFF badge).
   - Available sizes (e.g. `S, M, L, XL, XXL` or `Free Size`).
   - Description and Fabric details (GSM, 100% Cotton, etc.).
   - Mark as Featured / Top Pick.
2. **Product Management:**
   - Toggle **In Stock / Sold Out** with 1 click.
   - Edit any existing product details or add more photos.
   - Delete products.
   - Search products dynamically.
3. **Store & WhatsApp Settings:**
   - Change your WhatsApp phone number anytime without touching code.
   - Change Store Name, Tagline, Email, Announcement Bar text.
   - Update Admin password.

---

## 📲 How Customer WhatsApp Ordering Works

1. Customer browses the stylish clothing catalog.
2. Clicks on any product or opens the Quick View modal to choose their size (`S`, `M`, `L`, `XL`, etc.).
3. Clicks **"Order on WhatsApp"**.
4. Customer's WhatsApp opens automatically with a pre-filled message containing:
   - Product Name
   - Selected Size
   - Price (₹)
   - Direct Product Link
5. You receive the exact order details on your WhatsApp (`+91 7851891611`) and can confirm payment (UPI / COD) and delivery address directly!
