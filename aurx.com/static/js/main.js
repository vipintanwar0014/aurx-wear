// AURX WEAR - Luxury Storefront Interactive Logic

let selectedModalSize = '';
let activeModalProduct = null;
const selectedCardSizes = {};

function handleSortChange(sortValue) {
    const url = new URL(window.location.href);
    url.searchParams.set('sort', sortValue);
    window.location.href = url.toString();
}

// Interactive card size picker
function selectCardSize(productId, size, buttonElement) {
    selectedCardSizes[productId] = size;
    const parent = buttonElement.parentElement;
    parent.querySelectorAll('.card-size-btn').forEach(btn => {
        btn.classList.remove('bg-white', 'text-black', 'border-white');
        btn.classList.add('bg-black', 'text-neutral-300', 'border-white/[0.08]');
    });
    buttonElement.classList.remove('bg-black', 'text-neutral-300', 'border-white/[0.08]');
    buttonElement.classList.add('bg-white', 'text-black', 'border-white');
}

// Universal Instant WhatsApp Opener (No popup blocker alerts, no permission popups)
function openWhatsAppDirectly(whatsappNum, messageText) {
    const cleanNum = (whatsappNum || '917851891611').toString().replace(/\D/g, '');
    const isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
    
    // Direct WhatsApp API URL (Universal Link for iOS & Android)
    const waUrl = `https://api.whatsapp.com/send?phone=${cleanNum}&text=${messageText}`;

    if (isMobile) {
        // Navigating the current window completely bypasses iOS Safari and Android Chrome
        // "This site is attempting to open a pop-up window" alert, directly opening the WhatsApp app!
        window.location.href = waUrl;
    } else {
        // On desktop, open in a new tab for WhatsApp Web
        window.open(waUrl, '_blank', 'noopener,noreferrer');
    }
}

// 1-Click WhatsApp Quick Order Generator
function quickOrderWhatsApp(title, price, defaultSize, slug, productId) {
    const settings = window.STORE_SETTINGS || {};
    const whatsappNum = settings.whatsapp_number || '917851891611';
    const storeName = settings.store_name || 'AURX WEAR';
    const currency = settings.currency_symbol || '₹';
    const selectedSize = (productId && selectedCardSizes[productId]) || defaultSize || 'Standard';
    const productUrl = `${window.location.origin}/product/${slug}`;

    const text = `👋 Hello ${storeName}!%0A%0AI want to order this item:%0A👕 *Product:* ${encodeURIComponent(title)}%0A📏 *Size:* ${encodeURIComponent(selectedSize)}%0A💰 *Price:* ${encodeURIComponent(currency)}${price}%0A🔗 *Product Link:* ${encodeURIComponent(productUrl)}%0A%0APlease let me know how to proceed with payment and delivery!`;

    // Track lead asynchronously without blocking user navigation
    try {
        const leadPayload = JSON.stringify({
            channel: 'WhatsApp Quick Order',
            product_title: title,
            message: `Size: ${selectedSize}, Price: ${currency}${price}`
        });
        if (navigator.sendBeacon) {
            navigator.sendBeacon('/api/track-lead', new Blob([leadPayload], { type: 'application/json' }));
        } else {
            fetch('/api/track-lead', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: leadPayload, keepalive: true }).catch(() => {});
        }
    } catch (e) {}

    openWhatsAppDirectly(whatsappNum, text);
}

// Open Quick View Modal
function openProductModal(productId) {
    const products = window.PRODUCTS_DATA || [];
    const product = products.find(p => String(p.id) === String(productId));
    if (!product) return;

    activeModalProduct = product;
    const settings = window.STORE_SETTINGS || {};
    const currency = settings.currency_symbol || '₹';

    // Populate Fields
    document.getElementById('modalTitle').innerText = product.title;
    document.getElementById('modalCategory').innerText = product.category;
    document.getElementById('modalPrice').innerText = `${currency}${product.price}`;
    
    // Original Price & Discount
    const origPriceEl = document.getElementById('modalOriginalPrice');
    const badgeEl = document.getElementById('modalDiscountBadge');
    if (product.original_price && product.original_price > product.price) {
        origPriceEl.innerText = `${currency}${product.original_price}`;
        origPriceEl.classList.remove('hidden');
        if (badgeEl) badgeEl.classList.add('hidden');
    } else {
        origPriceEl.classList.add('hidden');
        if (badgeEl) badgeEl.classList.add('hidden');
    }

    // Images
    const mainImg = document.getElementById('modalMainImg');
    mainImg.src = product.primary_image;

    const thumbsContainer = document.getElementById('modalThumbnails');
    thumbsContainer.innerHTML = '';
    if (product.image_list && product.image_list.length > 1) {
        product.image_list.forEach((imgUrl, idx) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'w-12 h-14 rounded-lg overflow-hidden border border-white/20 hover:border-white shrink-0 bg-neutral-900 transition cursor-pointer';
            btn.innerHTML = `<img src="${imgUrl}" class="w-full h-full object-cover">`;
            btn.onclick = () => { mainImg.src = imgUrl; };
            thumbsContainer.appendChild(btn);
        });
        thumbsContainer.classList.remove('hidden');
    } else {
        thumbsContainer.classList.add('hidden');
    }

    // Description & Fabric
    document.getElementById('modalDescription').innerText = product.description || 'Premium heavyweight streetwear piece engineered with luxury quality fabrics and high durability standards.';
    const fabricContainer = document.getElementById('modalFabricContainer');
    if (product.fabric_details) {
        document.getElementById('modalFabric').innerText = product.fabric_details;
        fabricContainer.classList.remove('hidden');
    } else {
        fabricContainer.classList.add('hidden');
    }

    // Sizes
    const sizesContainer = document.getElementById('modalSizeButtons');
    sizesContainer.innerHTML = '';
    const sizes = product.size_list || ['Standard'];
    selectedModalSize = (selectedCardSizes[product.id]) || sizes[0];
    document.getElementById('selectedSizeLabel').innerText = selectedModalSize;

    sizes.forEach(sz => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `modal-size-pill px-3 py-1.5 rounded-lg text-xs font-mono font-bold border transition cursor-pointer ${
            sz === selectedModalSize 
                ? 'bg-white text-black border-white' 
                : 'bg-black text-white border-white/[0.08] hover:border-neutral-400'
        }`;
        btn.innerText = sz;
        btn.onclick = () => {
            selectedModalSize = sz;
            selectedCardSizes[product.id] = sz;
            document.getElementById('selectedSizeLabel').innerText = sz;
            document.querySelectorAll('.modal-size-pill').forEach(b => {
                b.className = 'modal-size-pill px-3 py-1.5 rounded-lg text-xs font-mono font-bold border transition bg-black text-white border-white/[0.08] hover:border-neutral-400 cursor-pointer';
            });
            btn.className = 'modal-size-pill px-3 py-1.5 rounded-lg text-xs font-mono font-bold border transition bg-white text-black border-white cursor-pointer';
        };
        sizesContainer.appendChild(btn);
    });

    // WhatsApp CTA inside Modal
    const orderBtn = document.getElementById('modalWhatsAppBtn');
    if (product.in_stock === 1) {
        orderBtn.disabled = false;
        orderBtn.className = 'w-full py-3.5 px-4 rounded-xl bg-white hover:bg-neutral-200 text-black font-heading font-black text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg transition active:scale-95 cursor-pointer';
        orderBtn.innerHTML = '<i class="fa-brands fa-whatsapp text-sm text-emerald-600"></i><span>Order on WhatsApp</span>';
        orderBtn.onclick = () => {
            const whatsappNum = settings.whatsapp_number || '917851891611';
            const storeName = settings.store_name || 'AURX WEAR';
            const productUrl = `${window.location.origin}/product/${product.slug}`;
            const text = `👋 Hello ${storeName}!%0A%0AI want to order this item:%0A👕 *Product:* ${encodeURIComponent(product.title)}%0A📏 *Size:* ${encodeURIComponent(selectedModalSize)}%0A💰 *Price:* ${encodeURIComponent(currency)}${product.price}%0A🔗 *Product Link:* ${encodeURIComponent(productUrl)}%0A%0APlease let me know how to proceed with payment and delivery!`;
            
            // Track lead asynchronously without blocking user navigation
            try {
                const leadPayload = JSON.stringify({
                    channel: 'Modal WhatsApp Order',
                    product_title: product.title,
                    message: `Size: ${selectedModalSize}, Price: ${currency}${product.price}`
                });
                if (navigator.sendBeacon) {
                    navigator.sendBeacon('/api/track-lead', new Blob([leadPayload], { type: 'application/json' }));
                } else {
                    fetch('/api/track-lead', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: leadPayload, keepalive: true }).catch(() => {});
                }
            } catch (e) {}

            openWhatsAppDirectly(whatsappNum, text);
        };
    } else {
        orderBtn.disabled = true;
        orderBtn.className = 'w-full py-3.5 px-4 rounded-xl bg-neutral-900 text-neutral-600 font-heading font-bold text-xs uppercase tracking-wider cursor-not-allowed text-center';
        orderBtn.innerHTML = '<span>Sold Out</span>';
    }

    // Show modal with animation
    const modal = document.getElementById('quickModal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
    }, 10);
    document.body.style.overflow = 'hidden';
}

function closeProductModal() {
    const modal = document.getElementById('quickModal');
    if (!modal) return;
    modal.classList.add('opacity-0');
    setTimeout(() => {
        modal.classList.remove('flex');
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }, 250);
}

// Close modal on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeProductModal();
    }
});

// Close modal when clicking outside backdrop
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('quickModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeProductModal();
            }
        });
    }
});
