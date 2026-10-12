// Экран «Свой продукт»: создание личного продукта, значения на 100 г.
import {
  initApp,
  setMainButton,
  setMainButtonLoading,
  setMainButtonEnabled,
  navigate,
  haptic,
  showToast,
  round1,
} from './app.js?v=20261013b';
import { createProduct } from './api.js?v=20261013b';

const NUMBER_FIELDS = [
  { key: 'calories', id: 'fieldCalories', label: 'Ккал', max: 900 },
  { key: 'protein', id: 'fieldProtein', label: 'Белки', max: 100 },
  { key: 'fat', id: 'fieldFat', label: 'Жиры', max: 100 },
  { key: 'carbs', id: 'fieldCarbs', label: 'Углеводы', max: 100 },
];

const el = {
  name: document.getElementById('fieldName'),
  brand: document.getElementById('fieldBrand'),
  calcHint: document.getElementById('calcHint'),
  calcBtn: document.getElementById('calcBtn'),
};

const numberInputs = NUMBER_FIELDS.map((field) => ({
  ...field,
  input: document.getElementById(field.id),
}));
for (const field of [
  { input: el.name },
  { input: el.brand },
  ...numberInputs,
]) {
  field.errorEl = field.input.parentElement.querySelector('.field-error');
}
const nameErrorEl = el.name.parentElement.querySelector('.field-error');

let isSaving = false;

function showError(input, errorEl, message) {
  input.classList.toggle('invalid', Boolean(message));
  if (errorEl) {
    errorEl.hidden = !message;
    errorEl.textContent = message || '';
  }
}

function parseNumber(text) {
  const value = text.trim().replace(',', '.');
  if (!/^\d+(\.\d+)?$/.test(value)) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function validate(showEmptyErrors = false) {
  let valid = true;
  const values = {};

  const name = el.name.value.trim().replace(/\s+/g, ' ');
  if (name.length < 2) {
    valid = false;
    showError(el.name, nameErrorEl, el.name.value && 'Минимум 2 символа');
  } else {
    showError(el.name, nameErrorEl, '');
  }
  values.name = name;
  values.brand = el.brand.value.trim().replace(/\s+/g, ' ') || null;

  for (const field of numberInputs) {
    const raw = field.input.value;
    const number = parseNumber(raw);
    const errorEl = field.errorEl;
    if (raw.trim() === '') {
      valid = false;
      showError(field.input, errorEl, showEmptyErrors ? 'Заполните поле' : '');
    } else if (number === null || number > field.max) {
      valid = false;
      showError(field.input, errorEl, `От 0 до ${field.max}`);
    } else {
      showError(field.input, errorEl, '');
      values[field.key] = number;
    }
  }

  // Подсказка: сколько калорий получается по БЖУ
  const { protein, fat, carbs } = values;
  const macrosOk = [protein, fat, carbs].every((v) => typeof v === 'number');
  el.calcHint.classList.remove('field-error');
  if (macrosOk && protein + fat + carbs > 100) {
    // На 100 г продукта белков, жиров и углеводов вместе не больше 100 г
    valid = false;
    el.calcHint.textContent =
      `Белки + жиры + углеводы = ${round1(protein + fat + carbs)} г, но на 100 г продукта их не может быть больше 100 г`;
    el.calcHint.classList.add('field-error');
    el.calcBtn.hidden = true;
  } else if (macrosOk) {
    const calc = Math.min(900, round1(4 * protein + 9 * fat + 4 * carbs));
    el.calcHint.textContent = `По БЖУ получается ${calc} ккал на 100 г`;
    el.calcBtn.hidden = false;
    el.calcBtn.dataset.value = String(calc);
  } else {
    el.calcHint.textContent = '';
    el.calcBtn.hidden = true;
  }

  setMainButtonEnabled(valid && !isSaving);
  return valid ? values : null;
}

async function save() {
  if (isSaving) return;
  const values = validate(true);
  if (!values) {
    haptic.error();
    return;
  }

  isSaving = true;
  setMainButtonLoading(true);
  try {
    const product = await createProduct({
      name: values.name,
      brand: values.brand,
      calories: values.calories,
      protein: values.protein,
      fat: values.fat,
      carbs: values.carbs,
    });
    haptic.success();
    try {
      sessionStorage.setItem('selectedProduct', JSON.stringify(product));
    } catch {
      // sessionStorage недоступен — экран добавления загрузит продукт по id
    }
    navigate('add.html', { product_id: product.id });
  } catch (err) {
    haptic.error();
    showToast(err.message || 'Не удалось сохранить продукт', 'error');
    isSaving = false;
    setMainButtonLoading(false);
    validate();
  }
}

initApp({ backTo: 'search.html' });
setMainButton('Сохранить', save);

const presetName = new URLSearchParams(location.search).get('name');
if (presetName) el.name.value = presetName.slice(0, 100);

[el.name, el.brand, ...numberInputs.map((f) => f.input)].forEach((input) => {
  input.addEventListener('input', () => validate());
});
el.calcBtn.addEventListener('click', () => {
  haptic.light();
  const field = numberInputs.find((f) => f.key === 'calories');
  field.input.value = String(el.calcBtn.dataset.value || '');
  validate();
});

validate();
