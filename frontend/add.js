// Экран «Добавление порции»: вес, предпросмотр КБЖУ, приём пищи.
import {
  initApp,
  setMainButton,
  setMainButtonLoading,
  setMainButtonEnabled,
  navigate,
  haptic,
  confirmDialog,
  showToast,
  todayLocal,
  round1,
  defaultMealType,
  displayBrand,
  foodEmoji,
} from './app.js?v=20261019a';
import { getProduct, addDiaryEntry, deleteProduct } from './api.js?v=20261019a';

const el = {
  media: document.getElementById('productMedia'),
  name: document.getElementById('productName'),
  brand: document.getElementById('productBrand'),
  per100: document.getElementById('productPer100'),
  weight: document.getElementById('weightInput'),
  weightError: document.getElementById('weightError'),
  previewKcal: document.getElementById('previewKcal'),
  previewMacros: document.getElementById('previewMacros'),
  mealButtons: document.querySelectorAll('#mealSwitch [data-meal]'),
  quickButtons: document.querySelectorAll('.quick-btn'),
  deleteBtn: document.getElementById('deleteProductBtn'),
};

const MIN_WEIGHT = 1;
const MAX_WEIGHT = 5000;

let product = null;
let mealType = defaultMealType();
let isSubmitting = false;

function readStoredProduct(id) {
  try {
    const raw = sessionStorage.getItem('selectedProduct');
    if (!raw) return null;
    const stored = JSON.parse(raw);
    return stored && Number(stored.id) === id ? stored : null;
  } catch {
    return null;
  }
}

function parseWeight() {
  const text = el.weight.value.trim().replace(',', '.');
  if (!/^\d+(\.\d+)?$/.test(text)) return null;
  const value = Number(text);
  if (!Number.isFinite(value) || value < MIN_WEIGHT || value > MAX_WEIGHT) return null;
  return value;
}

function createAvatar(name) {
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = foodEmoji(name);
  return avatar;
}

function renderProduct() {
  el.media.replaceChildren();
  if (typeof product.image_url === 'string' && product.image_url.startsWith('https://')) {
    const img = document.createElement('img');
    img.className = 'product-thumb';
    img.alt = '';
    img.src = product.image_url;
    img.addEventListener('error', () => img.replaceWith(createAvatar(product.name)));
    el.media.append(img);
  } else {
    el.media.append(createAvatar(product.name));
  }
  el.deleteBtn.hidden = product.source !== 'user';
  el.name.textContent = product.name;
  el.brand.textContent = displayBrand(product.brand);
  el.per100.textContent =
    `На 100 г: ${product.calories} ккал · Б ${product.protein} · Ж ${product.fat} · У ${product.carbs}`;
  updatePreview();
}

function updatePreview() {
  const weight = parseWeight();
  const valid = weight !== null;
  el.weight.classList.toggle('invalid', !valid);
  el.weightError.hidden = valid;
  setMainButtonEnabled(valid && product !== null && !isSubmitting);

  if (!valid || product === null) {
    el.previewKcal.textContent = '— ккал';
    el.previewMacros.textContent = '';
    return;
  }
  const calc = (per100) => round1((per100 * weight) / 100);
  el.previewKcal.textContent = `${calc(product.calories)} ккал`;
  el.previewMacros.textContent =
    `Б ${calc(product.protein)} · Ж ${calc(product.fat)} · У ${calc(product.carbs)} г`;
}

function selectMeal(meal) {
  mealType = meal;
  el.mealButtons.forEach((button) => {
    button.classList.toggle('active', button.dataset.meal === meal);
  });
}

async function submit() {
  if (isSubmitting || product === null) return;
  const weight = parseWeight();
  if (weight === null) return;

  isSubmitting = true;
  setMainButtonLoading(true);
  try {
    await addDiaryEntry({
      product_id: product.id,
      weight_g: weight,
      meal_type: mealType,
      entry_date: todayLocal(),
    });
    haptic.success();
    navigate('index.html');
  } catch (err) {
    haptic.error();
    showToast(err.message || 'Не удалось добавить запись', 'error');
    isSubmitting = false;
    setMainButtonLoading(false);
    updatePreview();
  }
}

async function onDeleteProduct() {
  if (!product || product.source !== 'user') return;
  const ok = await confirmDialog(`Удалить «${product.name}» из ваших продуктов?`);
  if (!ok) return;
  try {
    await deleteProduct(product.id);
    haptic.success();
    showToast('Продукт удалён', 'success');
    navigate('search.html');
  } catch (err) {
    haptic.error();
    showToast(err.message || 'Не удалось удалить продукт', 'error');
  }
}

async function init() {
  initApp({ backTo: 'search.html' });

  const params = new URLSearchParams(location.search);
  const rawId = params.get('product_id');
  const productId = rawId !== null && /^\d+$/.test(rawId) ? Number(rawId) : NaN;
  if (!Number.isInteger(productId) || productId <= 0) {
    showToast('Продукт не выбран', 'error');
    navigate('search.html');
    return;
  }

  setMainButton('Добавить', submit);
  selectMeal(mealType);
  updatePreview();

  el.weight.addEventListener('input', updatePreview);
  el.deleteBtn.addEventListener('click', onDeleteProduct);
  el.quickButtons.forEach((button) => {
    button.addEventListener('click', () => {
      haptic.light();
      el.weight.value = button.dataset.weight;
      updatePreview();
    });
  });
  el.mealButtons.forEach((button) => {
    button.addEventListener('click', () => {
      haptic.select();
      selectMeal(button.dataset.meal);
    });
  });

  const stored = readStoredProduct(productId);
  if (stored) {
    product = stored;
    renderProduct();
  }

  try {
    product = await getProduct(productId);
    renderProduct();
  } catch (err) {
    if (err.status === 404) {
      haptic.error();
      showToast('Продукт не найден', 'error');
      navigate('search.html');
      return;
    }
    if (!stored) {
      haptic.error();
      showToast(err.message || 'Не удалось загрузить продукт', 'error');
    }
  }
}

init();
