const API_BASE = "http://127.0.0.1:5000/api";
let livePollInterval = null;

function triggerScrape() {
    const btn = document.getElementById("btnScrape");
    btn.innerText = "⏳ Synchronizing System Feeds...";
    btn.disabled = true;

    fetch(`${API_BASE}/scrape`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pages: 3 })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        let pollCount = 0;
        loadCars();
        
        livePollInterval = setInterval(() => {
            loadCars();
            pollCount++;
            if (pollCount >= 6) {
                clearInterval(livePollInterval);
                btn.innerText = "⚡ Scrape Live Data";
                btn.disabled = false;
            }
        }, 2000);
    })
    .catch(err => {
        console.error(err);
        btn.innerText = "⚡ Scrape Live Data";
        btn.disabled = false;
    });
}

function loadCars() {
    const province = document.getElementById("filterProvince").value;
    const trans = document.getElementById("filterTrans").value;
    
    // UI Metric text updater
    document.getElementById("activeFilters").innerText = province ? `${province} Only` : "All Regions";

    let url = `${API_BASE}/cars?`;
    if (province) url += `province=${province}&`;
    if (trans) url += `transmission=${trans}&`;

    fetch(url)
    .then(res => res.json())
    .then(resData => {
        if (resData.status === "success") {
            document.getElementById("carCount").innerText = resData.count;
            const container = document.getElementById("carContainer");
            
            if (resData.data.length === 0) {
                container.innerHTML = '<div class="empty-state"><p>No matched data found for this region selection.</p><small>Click Scrape Live Data to populate dynamic profiles!</small></div>';
                return;
            }

            container.innerHTML = "";
            resData.data.forEach(car => {
                const item = document.createElement("div");
                item.className = "car-item";
                item.innerHTML = `
                    <div class="details-block">
                        <h4>${car.title}</h4>
                        <div class="badge-row">
                            <span class="badge badge-province">📍 ${car.province} (${car.city})</span>
                            <span class="badge">⚙️ ${car.transmission}</span>
                            <span class="badge">🚗 ${car.year}</span>
                            <span class="badge">🛣️ ${car.mileage.toLocaleString()} KM</span>
                        </div>
                    </div>
                    <div>
                        <div class="price-tag">PKR ${(car.price / 100000).toFixed(1)} Lac</div>
                    </div>
                `;
                container.appendChild(item);
            });
        }
    })
    .catch(err => console.error("Error running feed fetch:", err));
}

function evaluateDeal() {
    const make = document.getElementById("evalMake").value;
    const model = document.getElementById("evalModel").value;
    const year = document.getElementById("evalYear").value;
    const price = document.getElementById("evalPrice").value;
    const transmission = document.getElementById("evalTrans").value;

    if (!make || !model || !year || !price) {
        alert("Please key in all valuation vectors!");
        return;
    }

    const resultBox = document.getElementById("evaluationResult");
    resultBox.style.display = "block";
    resultBox.style.background = "#cbd5e1";
    resultBox.style.color = "#0f172a";
    resultBox.innerText = "Processing market indicators...";

    fetch(`${API_BASE}/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ make, model, year, price, transmission })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "success") {
            const evalData = data.evaluation;
            if(evalData.market_average) {
                resultBox.innerText = `${evalData.status}\n(Market Benchmark: PKR ${(evalData.market_average / 100000).toFixed(1)} Lac across ${evalData.total_listings_compared} reference logs)`;
                
                if (evalData.status.includes("Great")) {
                    resultBox.style.background = "#d1fae5"; resultBox.style.color = "#065f46"; resultBox.style.borderColor = "#10b981";
                } else if (evalData.status.includes("Overpriced")) {
                    resultBox.style.background = "#fee2e2"; resultBox.style.color = "#991b1b"; resultBox.style.borderColor = "#ef4444";
                } else {
                    resultBox.style.background = "#fef3c7"; resultBox.style.color = "#92400e"; resultBox.style.borderColor = "#f59e0b";
                }
            } else {
                resultBox.innerText = evalData.status;
                resultBox.style.background = "#fef3c7"; resultBox.style.color = "#92400e";
            }
        }
    })
    .catch(err => {
        console.error(err);
        resultBox.innerText = "Error completing diagnostic parsing execution.";
    });
}

window.onload = loadCars;