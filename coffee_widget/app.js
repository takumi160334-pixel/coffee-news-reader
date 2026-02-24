// Configuration
// In production, this URL will point to the GitHub Pages URL of the user
// Fetching logic below attempts multiple paths seamlessly.
// Financial API Proxy endpoints to bypass CORS for client-side fetching
// Using Yahoo Finance via a public proxy/API wrapper for demonstration purposes
const API_URL_ARABICA = 'https://query1.finance.yahoo.com/v8/finance/chart/KC=F?interval=1d';
const API_URL_ROBUSTA = 'https://query1.finance.yahoo.com/v8/finance/chart/RC=F?interval=1d';

// DOM Elements
const arabicaPriceEl = document.getElementById('arabica-price');
const arabicaChangeEl = document.getElementById('arabica-change');
const robustaPriceEl = document.getElementById('robusta-price');
const robustaChangeEl = document.getElementById('robusta-change');
const marketUpdatedEl = document.getElementById('market-updated');

const newsContainerEl = document.getElementById('news-container');
const newsUpdatedEl = document.getElementById('news-updated');
const refreshBtn = document.getElementById('refresh-btn');

/**
 * Format timestamp to short time string
 */
function formatTime(date) {
    return date.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
}

/**
 * Update UI for a specific commodity
 */
function updateCommodityUI(ticker, price, change, percent) {
    const isArabica = ticker === 'KC=F';
    const priceEl = isArabica ? arabicaPriceEl : robustaPriceEl;
    const changeEl = isArabica ? arabicaChangeEl : robustaChangeEl;

    // Formatting
    const decimals = isArabica ? 2 : 0;
    priceEl.textContent = price.toFixed(decimals);

    // Update change indicator
    const changeIcon = changeEl.querySelector('.change-icon');
    const changeVal = changeEl.querySelector('.change-value');
    const changePct = changeEl.querySelector('.change-pct');

    changeVal.textContent = Math.abs(change).toFixed(decimals);
    changePct.textContent = `(${Math.abs(percent).toFixed(2)}%)`;

    // Reset classes
    changeEl.className = 'price-change';

    if (change > 0) {
        changeEl.classList.add('up');
        changeIcon.textContent = '▲';
    } else if (change < 0) {
        changeEl.classList.add('down');
        changeIcon.textContent = '▼';
    } else {
        changeEl.classList.add('neutral');
        changeIcon.textContent = '-';
    }
}

/**
 * Fetch and Render Data from our generated JSON
 */
async function fetchAndRenderData() {
    newsContainerEl.innerHTML = `
        <div class="loading-state">
            <div class="spinner"></div>
            <p>Loading latest data...</p>
        </div>
    `;

    try {
        let response;
        // Try multiple paths to support both production (GH Pages) and local dev
        const possibleUrls = ['../news.json', '../public/news.json', './news.json'];

        for (const url of possibleUrls) {
            try {
                response = await fetch(url + "?t=" + new Date().getTime()); // cache buster
                if (response.ok) break;
            } catch {
                continue;
            }
        }

        if (response && response.ok) {
            const data = await response.json();

            // 1. Render News
            renderNews(data.articles);
            const updatedDate = new Date(data.updated_at);
            newsUpdatedEl.textContent = `News Generated: ${updatedDate.toLocaleDateString('ja-JP')} ${formatTime(updatedDate)}`;
            marketUpdatedEl.textContent = `Market Data: ${updatedDate.toLocaleDateString('ja-JP')} ${formatTime(updatedDate)}`;

            // 2. Render Market Data (if available in JSON)
            try {
                if (data.market_data) {
                    if (data.market_data.arabica) {
                        const meta = data.market_data.arabica;
                        const prevClose = meta.chartPreviousClose || meta.previousClose;
                        updateCommodityUI('KC=F', meta.regularMarketPrice, meta.regularMarketPrice - prevClose, ((meta.regularMarketPrice - prevClose) / prevClose) * 100);
                    }
                    if (data.market_data.robusta) {
                        const meta = data.market_data.robusta;
                        const prevClose = meta.chartPreviousClose || meta.previousClose;
                        updateCommodityUI('RC=F', meta.regularMarketPrice, meta.regularMarketPrice - prevClose, ((meta.regularMarketPrice - prevClose) / prevClose) * 100);
                    }
                }
            } catch (marketErr) {
                console.warn("Could not parse market data from JSON: ", marketErr);
            }

        } else {
            // Provide dummy data for visual testing if local json is not accessible
            renderDemoNews();
        }
    } catch (error) {
        console.error("Failed to fetch data:", error);
        renderDemoNews(); // Fallback for UI visualization
    }
}

/**
 * Render news items to DOM
 */
function renderNews(articles) {
    if (!articles || articles.length === 0) {
        newsContainerEl.innerHTML = `<div class="loading-state"><p>No new coffee articles found today.</p></div>`;
        return;
    }

    let html = '';
    articles.forEach(article => {
        html += `
            <div class="news-item">
                <div class="news-category">${article.category}</div>
                <a href="${article.link}" target="_blank" rel="noopener noreferrer" class="news-title">
                    ${article.title}
                </a>
                <div class="news-summary">${article.summary.replace(/\\n/g, '<br>')}</div>
            </div>
        `;
    });

    newsContainerEl.innerHTML = html;
}

/**
 * Fallback dummy data for visualization before GitHub Pages is live
 */
function renderDemoNews() {
    const demoArticles = [
        {
            category: "🌐 COFFEE TRENDS",
            title: "(Demo) Arabica prices hit new multi-year highs",
            link: "#",
            summary: "アナリストは今四半期の供給不足を指摘しています。ブラジルの天候不順が主な要因とみられています。"
        },
        {
            category: "🌱 FARM TO CUP",
            title: "(Demo) New sustainability report by major roasters",
            link: "#",
            summary: "主要ロースター数社が共同でサステナビリティに関するイニシアチブを発表。生産地とのダイレクトトレードを強化する方針。"
        },
        {
            category: "☕ BREW & GEAR",
            title: "(Demo) Review: The ultimate prosumer espresso machine?",
            link: "#",
            summary: "新しいダブルボイラーマシンの徹底レビュー。温度安定性と抽出の正確さが評価され、ホームバリスタの間で話題です。"
        }
    ];
    renderNews(demoArticles);
    newsUpdatedEl.textContent = "Data Source: Demo Mode (Waiting for GH Pages)";
    marketUpdatedEl.textContent = "Data Source: Demo Mode";
}

/**
 * Initialize Widget
 */
function init() {
    fetchAndRenderData();

    refreshBtn.addEventListener('click', () => {
        const icon = refreshBtn.querySelector('svg');
        icon.style.animation = 'spin 0.5s linear';

        fetchAndRenderData();

        setTimeout(() => {
            icon.style.animation = '';
        }, 500);
    });

    // Auto refresh data every 5 minutes (even though underlying JSON only changes daily)
    setInterval(fetchAndRenderData, 5 * 60 * 1000);
}

// Start app
document.addEventListener('DOMContentLoaded', init);
