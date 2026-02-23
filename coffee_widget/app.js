// Configuration
// In production, this URL will point to the GitHub Pages URL of the user
// e.g., 'https://takumi.github.io/coffee_news_reader/news.json'
const NEWS_JSON_URL = '../public/news.json'; // using local path for dev testing

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
 * Fetch Market Data (Futures Prices)
 * Note: Direct fetching from Yahoo Finance in browser might fail due to CORS. 
 * In a real production environment without a proxy, we'd use a dedicated stock API service.
 * Here we use an alternate free public proxy pattern if direct fails.
 */
async function fetchMarketData() {
    try {
        // We use allorigins.win as a free CORS proxy for Yahoo Finance API
        const arabicaUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(API_URL_ARABICA)}`;
        const robustaUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(API_URL_ROBUSTA)}`;

        const [arabicaRes, robustaRes] = await Promise.all([
            fetch(arabicaUrl),
            fetch(robustaUrl)
        ]);

        if (arabicaRes.ok && robustaRes.ok) {
            const arabicaProxy = await arabicaRes.json();
            const robustaProxy = await robustaRes.json();

            const arabicaData = JSON.parse(arabicaProxy.contents);
            const robustaData = JSON.parse(robustaProxy.contents);

            // Process Arabica
            if (arabicaData.chart.result) {
                const meta = arabicaData.chart.result[0].meta;
                updateCommodityUI('KC=F', meta.regularMarketPrice, meta.regularMarketPrice - meta.previousClose, ((meta.regularMarketPrice - meta.previousClose) / meta.previousClose) * 100);
            }

            // Process Robusta
            if (robustaData.chart.result) {
                const meta = robustaData.chart.result[0].meta;
                updateCommodityUI('RC=F', meta.regularMarketPrice, meta.regularMarketPrice - meta.previousClose, ((meta.regularMarketPrice - meta.previousClose) / meta.previousClose) * 100);
            }

            marketUpdatedEl.textContent = `Market Data: ${formatTime(new Date())}`;
        }
    } catch (error) {
        console.error("Failed to fetch market data:", error);
        marketUpdatedEl.textContent = "Data load failed (CORS/Network)";
    }
}

/**
 * Fetch and Render News Data
 */
async function fetchNewsData() {
    newsContainerEl.innerHTML = `
        <div class="loading-state">
            <div class="spinner"></div>
            <p>Loading latest articles...</p>
        </div>
    `;

    try {
        // In local development, if fetching the local file fails due to CORS (file://), 
        // fallback to just showing it's a demo.
        let response;
        try {
            response = await fetch(NEWS_JSON_URL + "?t=" + new Date().getTime()); // cache buster
        } catch {
            response = { ok: false };
        }

        if (response.ok) {
            const data = await response.json();
            renderNews(data.articles);

            const updatedDate = new Date(data.updated_at);
            newsUpdatedEl.textContent = `News Generated: ${updatedDate.toLocaleDateString('ja-JP')} ${formatTime(updatedDate)}`;
        } else {
            // Provide dummy data for visual testing if local json is not accessible
            renderDemoNews();
        }
    } catch (error) {
        console.error("Failed to fetch news:", error);
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
}

/**
 * Initialize Widget
 */
function init() {
    fetchMarketData();
    fetchNewsData();

    refreshBtn.addEventListener('click', () => {
        const icon = refreshBtn.querySelector('svg');
        icon.style.animation = 'spin 0.5s linear';

        fetchMarketData();
        fetchNewsData();

        setTimeout(() => {
            icon.style.animation = '';
        }, 500);
    });

    // Auto refresh market data every 5 minutes
    setInterval(fetchMarketData, 5 * 60 * 1000);
}

// Start app
document.addEventListener('DOMContentLoaded', init);
