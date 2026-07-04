const API = "/api";

const el = {
  scrapeBtn: document.getElementById("scrapeBtn"),
  scrapeDot: document.getElementById("scrapeDot"),
  scrapeStatusText: document.getElementById("scrapeStatusText"),
  provinceSelect: document.getElementById("provinceSelect"),
  citySelect: document.getElementById("citySelect"),
  transmissionSelect: document.getElementById("transmissionSelect"),
  makeInput: document.getElementById("makeInput"),
  makeList: document.getElementById("makeList"),
  modelInput: document.getElementById("modelInput"),
  modelList: document.getElementById("modelList"),
  yearMin: document.getElementById("yearMin"),
  yearMax: document.getElementById("yearMax"),
  priceMin: document.getElementById("priceMin"),
  priceMax: document.getElementById("priceMax"),
  applyFilters: document.getElementById("applyFilters"),
  resetFilters: document.getElementById("resetFilters"),
  resultsGrid: document.getElementById("resultsGrid"),
  resultsCount: document.getElementById("resultsCount"),
  emptyState: document.getElementById("emptyState"),
  cardTemplate: document.getElementById("cardTemplate"),
};

let pollTimer = null;

function formatPKR(value) {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-PK").format(Math.round(value));
}

async function loadFilters() {
  const res = await fetch(`${API}/filters`);
  const data = await res.json();

  fillSelect(el.provinceSelect, data.provinces);
  fillSelect(el.citySelect, data.cities);
  fillDatalist(el.makeList, data.makes);
  fillDatalist(el.modelList, data.models);
}

function fillSelect(selectEl, values) {
  const current = selectEl.value;
  [...selectEl.querySelectorAll("option[data-dynamic]")].forEach((o) => o.remove());
  values.forEach((v) => {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    opt.dataset.dynamic = "1";
    selectEl.appendChild(opt);
  });
  if (values.includes(current)) selectEl.value = current;
}

function fillDatalist(datalistEl, values) {
  datalistEl.innerHTML = "";
  values.forEach((v) => {
    const opt = document.createElement("option");
    opt.value = v;
    datalistEl.appendChild(opt);
  });
}

function buildQuery() {
  const params = new URLSearchParams();
  const add = (key, value) => { if (value) params.set(key, value); };

  add("province", el.provinceSelect.value);
  add("city", el.citySelect.value);
  add("transmission", el.transmissionSelect.value);
  add("make", el.makeInput.value.trim());
  add("model", el.modelInput.value.trim());
  add("year_min", el.yearMin.value);
  add("year_max", el.yearMax.value);
  add("price_min", el.priceMin.value);
  add("price_max", el.priceMax.value);

  return params.toString();
}

async function loadCars() {
  const query = buildQuery();
  const res = await fetch(`${API}/cars?${query}`);
  const data = await res.json();
  renderCars(data.results);
  el.resultsCount.textContent = `${data.count} listing${data.count === 1 ? "" : "s"}`;
}

function renderCars(cars) {
  el.resultsGrid.innerHTML = "";

  if (!cars.length) {
    el.emptyState.classList.add("visible");
    return;
  }
  el.emptyState.classList.remove("visible");

  cars.forEach((car) => {
    const node = el.cardTemplate.content.cloneNode(true);

    const img = node.querySelector(".car-image img");
    img.src = car.image_url || "";
    img.alt = car.title || "Car listing";
    if (!car.image_url) node.querySelector(".car-image").style.opacity = "0.3";

    node.querySelector(".car-title").textContent = car.title || "Untitled listing";
    node.querySelector(".odometer-value").textContent = formatPKR(car.price);

    node.querySelector(".chip-year").textContent = car.year || "";
    node.querySelector(".chip-mileage").textContent = car.mileage ? `${formatPKR(car.mileage)} km` : "";
    node.querySelector(".chip-fuel").textContent = car.fuel_type || "";
    node.querySelector(".chip-transmission").textContent = car.transmission || "";

    node.querySelector(".car-city").textContent = car.registration_city || "";
    const link = node.querySelector(".car-link");
    link.href = car.listing_url || "#";

    el.resultsGrid.appendChild(node);
  });
}

function setScrapeUI(state) {
  el.scrapeDot.classList.remove("running", "done", "error");
  if (state.running) {
    el.scrapeDot.classList.add("running");
    el.scrapeStatusText.textContent = "scraping…";
    el.scrapeBtn.disabled = true;
  } else if (state.error) {
    el.scrapeDot.classList.add("error");
    el.scrapeStatusText.textContent = "error";
    el.scrapeBtn.disabled = false;
  } else if (state.last_result) {
    el.scrapeDot.classList.add("done");
    const r = state.last_result;
    el.scrapeStatusText.textContent = `done · ${r.saved} saved`;
    el.scrapeBtn.disabled = false;
  } else {
    el.scrapeStatusText.textContent = "idle";
    el.scrapeBtn.disabled = false;
  }
}

async function pollScrapeStatus() {
  const res = await fetch(`${API}/scrape/status`);
  const state = await res.json();
  setScrapeUI(state);

  if (state.running) {
    pollTimer = setTimeout(pollScrapeStatus, 1500);
  } else {
    clearTimeout(pollTimer);
    await loadFilters();
    await loadCars();
  }
}

el.scrapeBtn.addEventListener("click", async () => {
  const res = await fetch(`${API}/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ max: 200 }),
  });
  if (res.status === 409) return; // already running
  pollScrapeStatus();
});

el.applyFilters.addEventListener("click", loadCars);

el.resetFilters.addEventListener("click", () => {
  [el.provinceSelect, el.citySelect, el.transmissionSelect].forEach((s) => (s.value = ""));
  [el.makeInput, el.modelInput, el.yearMin, el.yearMax, el.priceMin, el.priceMax].forEach((i) => (i.value = ""));
  loadCars();
});

(async function init() {
  await loadFilters();
  await loadCars();
  pollScrapeStatus();
})();