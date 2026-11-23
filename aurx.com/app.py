import os
import uuid
import json
import secrets
import hashlib
from datetime import datetime
from typing import List, Optional
from PIL import Image

from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

import database

# Initialize database schema & seed initial security/store metrics
database.init_db()

app = FastAPI(title="AURX WEAR Clothing Catalog & Admin Portal")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
try:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
except Exception:
    UPLOAD_DIR = "/tmp/uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        settings = database.get_settings()
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={"settings": settings},
            status_code=404
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# ---------------------------------------------------------------------------
# VISITOR TRAFFIC TRACKING & SECURITY HELPERS
# ---------------------------------------------------------------------------

def get_client_ip(request: Request) -> str:
    """Extract real client IP considering forward headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

def detect_device(user_agent: str) -> str:
    ua = user_agent.lower()
    if any(m in ua for m in ["iphone", "android", "mobile", "ipod", "blackberry"]):
        return "Mobile"
    if any(t in ua for t in ["ipad", "tablet"]):
        return "Tablet"
    return "Desktop"

def is_admin(request: Request) -> bool:
    """Verify admin session token against database-backed active sessions."""
    session_token = request.cookies.get("aurx_admin_auth")
    if not session_token:
        return False
    return database.is_session_valid(session_token)

def optimize_and_save_image(upload_file: UploadFile) -> Optional[str]:
    try:
        ext = os.path.splitext(upload_file.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
            ext = '.jpg'
        
        filename = f"prod_{uuid.uuid4().hex[:12]}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)

        image = Image.open(upload_file.file)
        
        # Convert RGBA to RGB if saving as JPG
        if image.mode in ("RGBA", "P") and ext in ['.jpg', '.jpeg']:
            image = image.convert("RGB")

        # Resize if width > 1200px maintaining aspect ratio
        max_width = 1200
        if image.width > max_width:
            ratio = max_width / float(image.width)
            new_height = int(float(image.height) * float(ratio))
            image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # Save optimized
        if ext in ['.jpg', '.jpeg']:
            image.save(filepath, "JPEG", quality=85, optimize=True)
        elif ext == '.webp':
            image.save(filepath, "WEBP", quality=85)
        else:
            image.save(filepath, optimize=True)

        return f"/static/uploads/{filename}"
    except Exception as e:
        print(f"Error saving image: {e}")
        return None

# Middleware to seamlessly track storefront traffic & unique visitors
@app.middleware("http")
async def track_visitors_middleware(request: Request, call_next):
    path = request.url.path
    response = await call_next(request)
    
    # Only track public storefront pages (ignore admin, static assets, internal endpoints)
    if not path.startswith("/static") and not path.startswith("/admin") and not path.startswith("/api"):
        try:
            visitor_id = request.cookies.get("aurx_vid")
            if not visitor_id:
                visitor_id = f"v_{uuid.uuid4().hex[:16]}"
                response.set_cookie(key="aurx_vid", value=visitor_id, max_age=86400 * 365, httponly=True)

            ip = get_client_ip(request)
            ip_hash = hashlib.sha256(f"salt_{ip}".encode()).hexdigest()[:16]
            ua = request.headers.get("user-agent", "Unknown")
            device_type = detect_device(ua)
            referrer = request.headers.get("referer", "Direct")

            database.record_site_visit(
                visitor_id=visitor_id,
                ip_hash=ip_hash,
                page_url=path,
                page_title="AURX WEAR Store",
                referrer=referrer,
                device_type=device_type,
                browser="Browser"
            )
        except Exception as e:
            print(f"Tracking error: {e}")

    return response

# ---------------------------------------------------------------------------
# PUBLIC STOREFRONT ROUTES
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, category: Optional[str] = None, q: Optional[str] = None, sort: Optional[str] = None):
    settings = database.get_settings()
    categories = database.get_all_categories()
    products = database.get_all_products(category=category, search=q, sort=sort)
    
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "settings": settings,
            "categories": categories,
            "products": products,
            "selected_category": category or "all",
            "search_query": q or "",
            "current_sort": sort or "featured"
        }
    )

@app.get("/product/{slug}", response_class=HTMLResponse)
async def product_detail(request: Request, slug: str):
    settings = database.get_settings()
    product = database.get_product_by_slug(slug)
    if not product:
        return RedirectResponse(url="/")
    
    related = database.get_all_products(category=product['category'])
    related = [p for p in related if p['id'] != product['id']][:4]

    return templates.TemplateResponse(
        request=request,
        name="product.html",
        context={
            "settings": settings,
            "product": product,
            "related": related
        }
    )

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    settings = database.get_settings()
    return templates.TemplateResponse(
        request=request,
        name="about.html",
        context={
            "settings": settings
        }
    )

@app.get("/contact")
async def contact_page():
    return RedirectResponse(url="/#contact", status_code=status.HTTP_302_FOUND)

# Track customer interest / WhatsApp order lead
@app.post("/api/track-lead")
async def track_lead(request: Request):
    try:
        data = await request.json()
        channel = data.get("channel", "WhatsApp Click")
        product_title = data.get("product_title", "")
        customer_name = data.get("customer_name", "Online Customer")
        contact = data.get("contact", "")
        msg = data.get("message", "")
        database.record_inquiry(channel, product_title, customer_name, contact, msg)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------------------------------------------------------------------
# ADMIN AUTHENTICATION WITH PBKDF2 & BRUTE-FORCE RATE LIMITING
# ---------------------------------------------------------------------------

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, error: Optional[str] = None):
    if is_admin(request):
        return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    settings = database.get_settings()
    
    client_ip = get_client_ip(request)
    is_locked = database.is_ip_locked(client_ip)
    
    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context={
            "settings": settings,
            "error": error,
            "is_locked": is_locked
        }
    )

@app.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)):
    client_ip = get_client_ip(request)
    
    # 1. Brute-Force Rate Limiting Lockout Check
    if database.is_ip_locked(client_ip):
        return RedirectResponse(
            url="/admin/login?error=Security+Alert:+Too+many+failed+attempts.+Access+locked+for+15+minutes.",
            status_code=status.HTTP_302_FOUND
        )

    # 2. Timing-safe PBKDF2 Password Verification
    is_valid = database.check_admin_password(password)
    
    if is_valid:
        # Success: record attempt & issue cryptographically random session token
        database.record_login_attempt(client_ip, True)
        session_token = secrets.token_urlsafe(32)
        ua = request.headers.get("user-agent", "")
        database.create_admin_session(session_token, client_ip, ua, max_age_seconds=86400 * 7)

        response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="aurx_admin_auth",
            value=session_token,
            httponly=True,
            max_age=86400 * 7,
            samesite="lax"
        )
        return response
    
    # Failed attempt: log attempt for lockout counter
    database.record_login_attempt(client_ip, False)
    return RedirectResponse(
        url="/admin/login?error=Access+Denied:+Invalid+master+password.+Attempt+logged.",
        status_code=status.HTTP_302_FOUND
    )

@app.get("/admin/logout")
async def admin_logout(request: Request):
    session_token = request.cookies.get("aurx_admin_auth")
    if session_token:
        database.delete_admin_session(session_token)
    response = RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="aurx_admin_auth")
    return response

# ---------------------------------------------------------------------------
# ADMIN COMMAND CENTER: DASHBOARD, SALES, RETURNS, PRODUCTS & TRAFFIC
# ---------------------------------------------------------------------------

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request, 
    msg: Optional[str] = None, 
    tab: Optional[str] = "orders",
    order_status: Optional[str] = None,
    order_search: Optional[str] = None,
    return_status: Optional[str] = None,
    return_search: Optional[str] = None
):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    settings = database.get_settings()
    analytics = database.get_dashboard_analytics()
    orders = database.get_all_orders(status_filter=order_status, search=order_search)
    returns = database.get_all_returns(status_filter=return_status, search=return_search)
    products = database.get_all_products()
    categories = database.get_all_categories()
    inquiries = database.get_all_inquiries(limit=25)

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "settings": settings,
            "analytics": analytics,
            "orders": orders,
            "returns": returns,
            "products": products,
            "categories": categories,
            "inquiries": inquiries,
            "active_tab": tab,
            "order_status_filter": order_status or "all",
            "return_status_filter": return_status or "all",
            "msg": msg
        }
    )

# Orders Management Endpoints
@app.post("/admin/order/update-status/{order_id}")
async def admin_update_order_status(
    order_id: int, 
    request: Request, 
    status: str = Form(...), 
    notes: Optional[str] = Form(None)
):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    database.update_order_status(order_id, status, notes)
    return RedirectResponse(url=f"/admin?msg=Order+status+updated+to+{status}!&tab=orders", status_code=302)

@app.post("/admin/order/delete/{order_id}")
async def admin_delete_order(order_id: int, request: Request):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    database.delete_order(order_id)
    return RedirectResponse(url="/admin?msg=Order+deleted+successfully!&tab=orders", status_code=302)

@app.post("/admin/order/create")
async def admin_create_order(
    request: Request,
    customer_name: str = Form(...),
    customer_phone: str = Form(...),
    customer_email: Optional[str] = Form(""),
    shipping_address: Optional[str] = Form(""),
    city: Optional[str] = Form(""),
    state: Optional[str] = Form(""),
    product_title: str = Form(...),
    size: str = Form("L"),
    quantity: int = Form(1),
    unit_price: int = Form(...),
    payment_method: str = Form("WhatsApp / UPI"),
    status: str = Form("Confirmed"),
    notes: Optional[str] = Form("")
):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    
    order_data = {
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_email": customer_email or "",
        "shipping_address": shipping_address or "",
        "city": city or "",
        "state": state or "",
        "product_title": product_title,
        "size": size,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_price": unit_price * quantity,
        "payment_method": payment_method,
        "status": status,
        "notes": notes or ""
    }
    order_num = database.create_order(order_data)
    return RedirectResponse(url=f"/admin?msg=New+order+{order_num}+created!&tab=orders", status_code=302)

# Returns & Refunds Endpoints
@app.post("/admin/return/update-status/{return_id}")
async def admin_update_return_status(
    return_id: int, 
    request: Request, 
    status: str = Form(...), 
    admin_notes: Optional[str] = Form(None)
):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    database.update_return_status(return_id, status, admin_notes)
    return RedirectResponse(url=f"/admin?msg=Return+ticket+updated+to+{status}!&tab=returns", status_code=302)

@app.post("/admin/return/create")
async def admin_create_return(
    request: Request,
    order_number: str = Form(...),
    customer_name: str = Form(...),
    customer_phone: str = Form(...),
    product_title: str = Form(...),
    size: Optional[str] = Form(""),
    amount: int = Form(...),
    reason: str = Form(...),
    status: str = Form("Pending Review"),
    admin_notes: Optional[str] = Form("")
):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    return_data = {
        "order_number": order_number,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "product_title": product_title,
        "size": size or "",
        "amount": amount,
        "reason": reason,
        "status": status,
        "admin_notes": admin_notes or ""
    }
    ret_num = database.create_return_request(return_data)
    return RedirectResponse(url=f"/admin?msg=Return+ticket+{ret_num}+logged!&tab=returns", status_code=302)

# Product Inventory Endpoints
@app.post("/admin/product/add")
async def admin_add_product(
    request: Request,
    title: str = Form(...),
    category: str = Form(...),
    price: int = Form(...),
    original_price: Optional[int] = Form(0),
    badge: Optional[str] = Form(""),
    sizes: Optional[str] = Form("S,M,L,XL"),
    description: Optional[str] = Form(""),
    fabric_details: Optional[str] = Form(""),
    is_featured: Optional[int] = Form(0),
    in_stock: Optional[int] = Form(1),
    images: List[UploadFile] = File([])
):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    saved_images = []
    for img in images:
        if img.filename and len(img.filename.strip()) > 0:
            saved_path = optimize_and_save_image(img)
            if saved_path:
                saved_images.append(saved_path)

    if not saved_images:
        saved_images = ["/static/images/logo.jpg"]

    database.add_category(category)

    product_data = {
        "title": title,
        "category": category,
        "price": price,
        "original_price": original_price or 0,
        "badge": badge or "",
        "sizes": sizes or "S,M,L,XL",
        "description": description or "",
        "fabric_details": fabric_details or "",
        "images": saved_images,
        "is_featured": 1 if is_featured else 0,
        "in_stock": 1 if in_stock else 0
    }

    database.add_product(product_data)
    return RedirectResponse(url="/admin?msg=Product+added+successfully!&tab=products", status_code=status.HTTP_302_FOUND)

@app.post("/admin/product/edit/{product_id}")
async def admin_edit_product(
    product_id: int,
    request: Request,
    title: str = Form(...),
    category: str = Form(...),
    price: int = Form(...),
    original_price: Optional[int] = Form(0),
    badge: Optional[str] = Form(""),
    sizes: Optional[str] = Form("S,M,L,XL"),
    description: Optional[str] = Form(""),
    fabric_details: Optional[str] = Form(""),
    is_featured: Optional[int] = Form(0),
    in_stock: Optional[int] = Form(1),
    existing_images: Optional[str] = Form("[]"),
    new_images: List[UploadFile] = File([])
):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    try:
        final_images = json.loads(existing_images) if existing_images else []
    except:
        final_images = []

    for img in new_images:
        if img.filename and len(img.filename.strip()) > 0:
            saved_path = optimize_and_save_image(img)
            if saved_path:
                final_images.append(saved_path)

    if not final_images:
        final_images = ["/static/images/logo.jpg"]

    database.add_category(category)

    product_data = {
        "title": title,
        "category": category,
        "price": price,
        "original_price": original_price or 0,
        "badge": badge or "",
        "sizes": sizes or "S,M,L,XL",
        "description": description or "",
        "fabric_details": fabric_details or "",
        "images": final_images,
        "is_featured": 1 if is_featured else 0,
        "in_stock": 1 if in_stock else 0
    }

    database.update_product(product_id, product_data)
    return RedirectResponse(url="/admin?msg=Product+updated+successfully!&tab=products", status_code=status.HTTP_302_FOUND)

@app.post("/admin/product/toggle-stock/{product_id}")
async def admin_toggle_stock(product_id: int, request: Request):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    database.toggle_product_stock(product_id)
    return RedirectResponse(url="/admin?msg=Stock+status+toggled!&tab=products", status_code=status.HTTP_302_FOUND)

@app.post("/admin/product/delete/{product_id}")
async def admin_delete_product(product_id: int, request: Request):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    database.delete_product(product_id)
    return RedirectResponse(url="/admin?msg=Product+deleted!&tab=products", status_code=status.HTTP_302_FOUND)

# Store Settings & Password Management
@app.post("/admin/settings")
async def admin_update_settings(
    request: Request,
    store_name: str = Form(...),
    tagline: str = Form(...),
    whatsapp_number: str = Form(...),
    email: str = Form(...),
    currency_symbol: str = Form(...),
    announcement_text: str = Form(...),
    banner_subtitle: str = Form(...),
    instagram_url: Optional[str] = Form("")
):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    clean_whatsapp = "".join(filter(str.isdigit, whatsapp_number))

    data = {
        "store_name": store_name,
        "tagline": tagline,
        "whatsapp_number": clean_whatsapp,
        "email": email,
        "currency_symbol": currency_symbol,
        "announcement_text": announcement_text,
        "banner_subtitle": banner_subtitle,
        "instagram_url": instagram_url or "https://instagram.com"
    }

    database.update_settings(data)
    return RedirectResponse(url="/admin?msg=Settings+saved+successfully!&tab=settings", status_code=status.HTTP_302_FOUND)

@app.post("/admin/change-password")
async def admin_change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...)
):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)

    if not database.check_admin_password(old_password):
        return RedirectResponse(url="/admin?msg=Error:+Current+master+password+is+incorrect!&tab=settings", status_code=status.HTTP_302_FOUND)

    if len(new_password) < 6:
        return RedirectResponse(url="/admin?msg=Error:+New+password+must+be+at+least+6+characters!&tab=settings", status_code=status.HTTP_302_FOUND)

    database.update_admin_password(new_password)
    return RedirectResponse(url="/admin?msg=Master+password+securely+updated+with+salted+PBKDF2+hash!&tab=settings", status_code=status.HTTP_302_FOUND)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
