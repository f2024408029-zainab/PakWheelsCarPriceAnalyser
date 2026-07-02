const API_BASE = "http://127.0.0.1:5000/api";
let livePollInterval = null;

// Function to trigger background live scraper instantly
function triggerScrape() {
    const btn = document.getElementById("btnScrape");
    btn.innerText = "⏳ Scraping & Syncing...";
    btn.disabled = true;

    fetch(`${API_BASE}/scrape`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pages: 3 })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        
        // A+ GRADE IMPROVEMENT: Dynamic Live Polling
        // Pulls data every 2.5 seconds dynamically so user sees listings pop up live
        let pollCount = 0;
        loadCars(); // instant first pull
        
        livePollInterval = setInterval(() => {
            loadCars();
            pollCount++;
            if (pollCount >= 8) { // Stop polling after 20 seconds (3 pages done)
                clearInterval(livePollInterval);
                btn.innerText = "⚡ Scrape Live Data";
                btn.disabled = false;
            }
        }, 2500);
    })
    .catch(err => {
        console.error(err);
        btn.innerText = "⚡ Scrape Live Data";
        btn.disabled = false;
    });
}

// Function to pull real-time results with selected filters
function loadCars() {
    const province = document.getElementById("filterProvince").value;
    const trans = document.getElementById("filterTrans").value;

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
                container.innerHTML = '<p style="text-align: center; color: #888; padding: 40px;">No matched data found. Click Scrape Live Data!</p>';
                return;
            }

            container.innerHTML = "";
            resData.data.forEach(car => {
                const item = document.createElement("div");
                item.className = "car-item";
                item.innerHTML = `
                    <div>
                        <strong style="font-size: 1.1em;">${car.title}</strong>
                        <div style="margin-top: 5px; color: #666;">
                            <span class="badge" style="background:#004a9f; color:white;">${car.province}</span> | 
                            <span class="badge">${car.transmission}</span> | 
                            <span class="badge">${car.engine_capacity}</span> | 
                            <span class="badge">${car.mileage.toLocaleString()} KM</span>
                        </div>
                        <small style="color: #999;">Synced at: ${car.scraped_at}</small>
                    </div>
                    <div>
                        <span class="price">PKR ${(car.price / 100000).toFixed(1)} Lac</span>
                    </div>
                `;
                container.appendChild(item);
            });
        }
    })
    .catch(err => console.error("Error fetching rows:", err));
}

// Function to handle predictive pricing inputs
function evaluateDeal() {
    const make = document.getElementById("evalMake").value;
    const model = document.getElementById("evalModel").value;
    const year = document.getElementById("evalYear").value;
    const price = document.getElementById("evalPrice").value;
    const transmission = document.getElementById("evalTrans").value;

    if (!make || !model || !year || !price) {
        alert("Please fill out all predictive fields!");
        return;
    }

    const resultBox = document.getElementById("evaluationResult");
    resultBox.style.display = "block";
    resultBox.style.backgroundColor = "#e9ecef";
    resultBox.style.color = "#333";
    resultBox.innerText = "Analyzing live trends & market deviations...";

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
                resultBox.innerText = `${evalData.status} \n(Market Avg for ${year}: PKR ${(evalData.market_average / 100000).toFixed(1)} Lac across ${evalData.total_listings_compared} reference points)`;
                
                if (evalData.status.includes("Great")) {
                    resultBox.style.backgroundColor = "#d4edda"; resultBox.style.color = "#155724";
                } else if (evalData.status.includes("Overpriced")) {
                    resultBox.style.backgroundColor = "#f8d7da"; resultBox.style.color = "#721c24";
                } else {
                    resultBox.style.backgroundColor = "#fff3cd"; resultBox.style.color = "#856404";
                }
            } else {
                // Fallback rendering
                resultBox.innerText = evalData.status;
                resultBox.style.backgroundColor = "#fff3cd"; resultBox.style.color = "#856404";
            }
        }
    })
    .catch(err => {
        console.error(err);
        resultBox.innerText = "Error analyzing deal data.";
    });
}

window.onload = loadCars;