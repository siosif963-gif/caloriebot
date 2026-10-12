// Экран «Поиск»: debounce, отмена предыдущего запроса, карточки продуктов.
import { initApp, navigate, haptic, displayBrand, foodEmoji } from './app.js?v=20261013b';
import { searchProducts } from './api.js?v=20261013b';

const DEBOUNCE_MS = 300;
const MIN_QUERY_LENGTH = 2;

const el = {
  input: document.getElementById('searchInput'),
  banner: document.getElementById('banner'),
  stateText: document.getElementById('stateText'),
  errorBox: document.getElementById('errorBox'),
  errorText: document.getElementById('errorText'),
  retryBtn: document.getElementById('retryBtn'),
  results: document.getElementById('results'),
  createBtn: document.getElementById('createBtn'),
};

let debounceTimer = null;
let currentController = null;
let requestCounter = 0;

function storageGet(key) {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function storageSet(key, value) {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    // sessionStorage недоступен — не критично
  }
}

function resetView() {
  el.banner.hidden = true;
  el.errorBox.hidden = true;
  el.stateText.textContent = '';
  el.results.replaceChildren();
}

function renderSkeletons() {
  resetView();
  for (let i = 0; i < 5; i += 1) {
    const skeleton = document.createElement('div');
    skeleton.className = 'skeleton skeleton-card';
    el.results.append(skeleton);
  }
}

function createAvatar(name) {
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = foodEmoji(name);
  return avatar;
}

function createMedia(product) {
  if (typeof product.image_url === 'string' && product.image_url.startsWith('https://')) {
    const img = document.createElement('img');
    img.className = 'product-thumb';
    img.loading = 'lazy';
    img.alt = '';
    img.src = product.image_url;
    img.addEventListener('error', () => img.replaceWith(createAvatar(product.name)));
    return img;
  }
  return createAvatar(product.name);
}

function renderCard(product) {
  const card = document.createElement('button');
  card.type = 'button';
  card.className = 'product-card';

  const info = document.createElement('div');
  info.className = 'product-info';
  const name = document.createElement('div');
  name.className = 'product-name';
  name.textContent = product.name;
  if (product.source === 'off' || product.source === 'user') {
    const badge = document.createElement('span');
    badge.className = 'badge';
    badge.textContent = product.source === 'user' ? 'МОЁ' : 'OFF';
    name.append(badge);
  }
  info.append(name);
  if (product.brand) {
    const brand = document.createElement('div');
    brand.className = 'hint';
    brand.textContent = displayBrand(product.brand);
    info.append(brand);
  }

  const kcal = document.createElement('div');
  kcal.className = 'product-kcal';
  kcal.textContent = `${product.calories} ккал / 100 г`;

  card.append(createMedia(product), info, kcal);
  card.addEventListener('click', () => {
    haptic.select();
    storageSet('selectedProduct', JSON.stringify(product));
    navigate('add.html', { product_id: product.id });
  });
  return card;
}

function renderResults(response) {
  resetView();
  el.banner.hidden = response.external_status !== 'unavailable';
  if (response.items.length === 0) {
    el.stateText.textContent = 'Продукт не найден. Попробуйте другое название';
    return;
  }
  response.items.forEach((product) => el.results.append(renderCard(product)));
}

function showError(message) {
  resetView();
  el.errorText.textContent = message;
  el.errorBox.hidden = false;
}

async function runSearch(query) {
  if (currentController) currentController.abort();
  const controller = new AbortController();
  currentController = controller;
  requestCounter += 1;
  const myRequest = requestCounter;

  renderSkeletons();
  try {
    const response = await searchProducts(query, controller.signal);
    if (myRequest !== requestCounter) return;
    renderResults(response);
  } catch (err) {
    if (err && err.name === 'AbortError') return;
    if (myRequest !== requestCounter) return;
    showError(err.message || 'Не удалось выполнить поиск');
  }
}

function onInput() {
  const query = el.input.value.trim();
  storageSet('lastSearchQuery', el.input.value);
  clearTimeout(debounceTimer);

  if (query.length < MIN_QUERY_LENGTH) {
    if (currentController) currentController.abort();
    requestCounter += 1;
    resetView();
    el.stateText.textContent = 'Введите хотя бы 2 символа';
    return;
  }
  debounceTimer = setTimeout(() => runSearch(query), DEBOUNCE_MS);
}

initApp({ backTo: 'index.html' });

el.input.addEventListener('input', onInput);
el.createBtn.addEventListener('click', () => {
  haptic.light();
  navigate('create.html', { name: el.input.value.trim() });
});
el.retryBtn.addEventListener('click', () => {
  haptic.light();
  const query = el.input.value.trim();
  if (query.length >= MIN_QUERY_LENGTH) runSearch(query);
});

const lastQuery = storageGet('lastSearchQuery');
if (lastQuery) {
  el.input.value = lastQuery;
}
el.input.focus();
onInput();
