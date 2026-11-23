// Admin Portal Interactivity

function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('border-white', 'text-white');
        btn.classList.add('border-transparent', 'text-neutral-400');
    });

    const activeContent = document.getElementById(`tabContent-${tabName}`);
    const activeBtn = document.getElementById(`tabBtn-${tabName}`);

    if (activeContent) activeContent.classList.remove('hidden');
    if (activeBtn) {
        activeBtn.classList.remove('border-transparent', 'text-neutral-400');
        activeBtn.classList.add('border-white', 'text-white');
    }

    // Update URL query param quietly
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tabName);
    window.history.replaceState({}, '', url.toString());
}

function previewUploadImages(input, previewContainerId) {
    const container = document.getElementById(previewContainerId);
    if (!container) return;
    container.innerHTML = '';

    if (input.files && input.files.length > 0) {
        Array.from(input.files).forEach(file => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const div = document.createElement('div');
                div.className = 'w-16 h-20 rounded-xl overflow-hidden bg-neutral-900 border border-brand-border relative shadow-md';
                div.innerHTML = `<img src="${e.target.result}" class="w-full h-full object-cover">`;
                container.appendChild(div);
            };
            reader.readAsDataURL(file);
        });
    }
}

function filterAdminTable() {
    const query = (document.getElementById('adminSearchInput').value || '').toLowerCase().trim();
    const rows = document.querySelectorAll('#adminProductsTable .product-row');
    
    rows.forEach(row => {
        const searchData = row.getAttribute('data-search') || '';
        if (searchData.includes(query)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

function openEditModal(productId) {
    const products = window.ADMIN_PRODUCTS || [];
    const product = products.find(p => p.id === productId);
    if (!product) return;

    document.getElementById('editProductForm').action = `/admin/product/edit/${product.id}`;
    document.getElementById('editTitle').value = product.title;
    document.getElementById('editCategory').value = product.category;
    document.getElementById('editPrice').value = product.price;
    document.getElementById('editOriginalPrice').value = product.original_price || '';
    document.getElementById('editBadge').value = product.badge || '';
    document.getElementById('editSizes').value = product.sizes || 'S,M,L,XL';
    document.getElementById('editDescription').value = product.description || '';
    document.getElementById('editFabricDetails').value = product.fabric_details || '';
    document.getElementById('editIsFeatured').checked = (product.is_featured === 1);
    document.getElementById('editInStock').checked = (product.in_stock === 1);
    document.getElementById('editExistingImages').value = JSON.stringify(product.image_list || []);

    const modal = document.getElementById('editProductModal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
    }, 10);
    document.body.style.overflow = 'hidden';
}

function closeEditModal() {
    const modal = document.getElementById('editProductModal');
    if (!modal) return;
    modal.classList.add('opacity-0');
    setTimeout(() => {
        modal.classList.remove('flex');
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }, 250);
}

// Close edit modal on escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeEditModal();
    }
});
