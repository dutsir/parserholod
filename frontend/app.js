
const API_BASE = '/api';


const state = {
    currentQuery: '',
    currentFilters: {}
};


const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const clearFiltersBtn = document.getElementById('clearFilters');
const resultsDiv = document.getElementById('results');
const resultsInfo = document.getElementById('resultsInfo');
const loadingDiv = document.getElementById('loading');
const noResultsDiv = document.getElementById('noResults');
const modal = document.getElementById('detailModal');
const modalBody = document.getElementById('modalBody');
const closeBtn = document.querySelector('.close');


document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadListings();
    
    searchBtn.addEventListener('click', handleSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSearch();
    });
    clearFiltersBtn.addEventListener('click', clearFilters);
    closeBtn.addEventListener('click', closeModal);
    window.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });
});


async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        
        document.getElementById('totalProducts').textContent = data.total_products;
        document.getElementById('totalOffers').textContent = data.total_offers;
        document.getElementById('avitoCount').textContent = data.offers_by_source.avito || 0;
        document.getElementById('farpostCount').textContent = data.offers_by_source.farpost || 0;
        document.getElementById('cianCount').textContent = data.offers_by_source.cian || 0;
    } catch (error) {
        console.error('Ошибка загрузки статистики:', error);
    }
}

async function loadListings(query = '', filters = {}) {
    showLoading();
    
    try {
        const params = new URLSearchParams({
            q: query,
            limit: 50,
            ...filters
        });
        
        for (let [key, value] of params.entries()) {
            if (!value) params.delete(key);
        }
        
        const response = await fetch(`${API_BASE}/search?${params}`);
        const data = await response.json();
        
        displayResults(data.results, data.total);
    } catch (error) {
        console.error('Ошибка загрузки объявлений:', error);
        showNoResults();
    }
}

function handleSearch() {
    const query = searchInput.value.trim();
    const filters = {
        min_price: document.getElementById('minPrice').value,
        max_price: document.getElementById('maxPrice').value,
        min_area: document.getElementById('minArea').value,
        max_area: document.getElementById('maxArea').value,
        rooms: document.getElementById('rooms').value
    };
    
    state.currentQuery = query;
    state.currentFilters = filters;
    
    loadListings(query, filters);
}

function clearFilters() {
    searchInput.value = '';
    document.getElementById('minPrice').value = '';
    document.getElementById('maxPrice').value = '';
    document.getElementById('minArea').value = '';
    document.getElementById('maxArea').value = '';
    document.getElementById('rooms').value = '';
    
    state.currentQuery = '';
    state.currentFilters = {};
    
    loadListings();
}

function displayResults(results, total) {
    hideLoading();
    
    if (!results || results.length === 0) {
        showNoResults();
        return;
    }
    
    noResultsDiv.style.display = 'none';
    resultsInfo.textContent = `Найдено: ${total} объектов`;
    
    resultsDiv.innerHTML = results.map(listing => `
        <div class="listing-card" onclick="showDetail(${listing.id})">
            <div class="listing-image">
                ${listing.image_url 
                    ? `<img src="${listing.image_url}" alt="${listing.canonical_title}" onerror="this.parentElement.innerHTML='🏠'">`
                    : '🏠'
                }
            </div>
            <div class="listing-content">
                <div class="listing-title">${escapeHtml(listing.canonical_title)}</div>
                <div class="listing-address">📍 ${escapeHtml(listing.canonical_address)}</div>
                <div class="listing-details">
                    <span>🛏️ ${listing.rooms} комн.</span>
                    <span>📐 ${listing.area} м²</span>
                </div>
                <div class="listing-price">${formatPrice(listing.min_price)} ₽/мес</div>
                <div class="listing-sources">
                    <span class="source-badge">${listing.offers_count} предложений</span>
                </div>
            </div>
        </div>
    `).join('');
}

async function showDetail(productId) {
    try {
        const response = await fetch(`${API_BASE}/listing/${productId}`);
        const data = await response.json();
        
        modalBody.innerHTML = `
            <div class="detail-header">
                <h2 class="detail-title">${escapeHtml(data.canonical_title)}</h2>
                <p class="listing-address">📍 ${escapeHtml(data.canonical_address)}</p>
            </div>
            
            <div class="detail-info">
                <div><strong>Комнат:</strong> ${data.rooms}</div>
                <div><strong>Площадь:</strong> ${data.area} м²</div>
                <div><strong>Тип:</strong> ${data.property_type}</div>
                <div><strong>Мин. цена:</strong> ${formatPrice(data.min_price)} ₽</div>
            </div>
            
            ${data.description ? `<p><strong>Описание:</strong><br>${escapeHtml(data.description)}</p>` : ''}
            
            <div class="detail-offers">
                <h3>Предложения с разных сайтов (${data.offers.length}):</h3>
                ${data.offers.map(offer => `
                    <div class="offer-item">
                        <div class="offer-source">${getSourceName(offer.website_name)}</div>
                        <div class="offer-price">${formatPrice(offer.price)} ₽/мес</div>
                        <div>${escapeHtml(offer.title)}</div>
                        <a href="${offer.url}" target="_blank" class="offer-link">Открыть объявление →</a>
                    </div>
                `).join('')}
            </div>
        `;
        
        modal.style.display = 'block';
    } catch (error) {
        console.error('Ошибка загрузки деталей:', error);
        alert('Ошибка загрузки деталей объявления');
    }
}


function closeModal() {
    modal.style.display = 'none';
}


function showLoading() {
    loadingDiv.style.display = 'block';
    resultsDiv.innerHTML = '';
    noResultsDiv.style.display = 'none';
}

function hideLoading() {
    loadingDiv.style.display = 'none';
}

function showNoResults() {
    hideLoading();
    resultsDiv.innerHTML = '';
    noResultsDiv.style.display = 'block';
    resultsInfo.textContent = '';
}

function formatPrice(price) {
    return new Intl.NumberFormat('ru-RU').format(price);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getSourceName(source) {
    const names = {
        'avito': 'Avito',
        'farpost': 'FarPost',
        'cian': 'CIAN'
    };
    return names[source] || source;
}

