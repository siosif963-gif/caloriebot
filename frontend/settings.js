// Экран «Настройки»: дневные нормы КБЖУ.
import {
  initApp,
  setMainButton,
  setMainButtonLoading,
  setMainButtonEnabled,
  haptic,
  showToast,
} from './app.js?v=20261013c';
import { getUser, updateSettings } from './api.js?v=20261013c';

// Диапазоны совпадают с UserSettingsUpdate на бэкенде
const FIELDS = [
  { inputId: 'fieldCalories', key: 'daily_calories', min: 800, max: 10000 },
  { inputId: 'fieldProtein', key: 'daily_protein', min: 0, max: 500 },
  { inputId: 'fieldFat', key: 'daily_fat', min: 0, max: 500 },
  { inputId: 'fieldCarbs', key: 'daily_carbs', min: 0, max: 1000 },
];

const el = {
  loading: document.getElementById('loading'),
  errorBox: document.getElementById('errorBox'),
  errorText: document.getElementById('errorText'),
  retryBtn: document.getElementById('retryBtn'),
  form: document.getElementById('form'),
  macroHint: document.getElementById('macroHint'),
};

const inputs = FIELDS.map((field) => ({
  ...field,
  input: document.getElementById(field.inputId),
}));
for (const field of inputs) {
  field.errorEl = field.input.parentElement.querySelector('.field-error');
}

let isSaving = false;

function showState(state) {
  el.loading.hidden = state !== 'loading';
  el.errorBox.hidden = state !== 'error';
  el.form.hidden = state !== 'form';
}

function parseField(field) {
  const text = field.input.value.trim();
  if (!/^\d+$/.test(text)) return null;
  const value = Number(text);
  return value >= field.min && value <= field.max ? value : null;
}

function validate() {
  let allValid = true;
  const values = {};
  for (const field of inputs) {
    const value = parseField(field);
    const valid = value !== null;
    field.input.classList.toggle('invalid', !valid);
    field.errorEl.hidden = valid;
    if (!valid) {
      field.errorEl.textContent = `Введите целое число от ${field.min} до ${field.max}`;
      allValid = false;
    }
    values[field.key] = value;
  }

  if (allValid) {
    const kcal = 4 * values.daily_protein + 9 * values.daily_fat + 4 * values.daily_carbs;
    el.macroHint.textContent = `По БЖУ получается ${kcal} ккал`;
  } else {
    el.macroHint.textContent = '';
  }
  setMainButtonEnabled(allValid && !isSaving);
  return allValid ? values : null;
}

async function save() {
  if (isSaving) return;
  const values = validate();
  if (!values) return;

  isSaving = true;
  setMainButtonLoading(true);
  try {
    await updateSettings(values);
    haptic.success();
    showToast('Сохранено', 'success');
  } catch (err) {
    haptic.error();
    showToast(err.message || 'Не удалось сохранить', 'error');
  } finally {
    isSaving = false;
    setMainButtonLoading(false);
    validate();
  }
}

async function load() {
  showState('loading');
  try {
    const user = await getUser();
    for (const field of inputs) {
      field.input.value = String(user[field.key]);
    }
    showState('form');
    validate();
  } catch (err) {
    el.errorText.textContent = err.message || 'Не удалось загрузить настройки';
    showState('error');
  }
}

initApp();
setMainButton('Сохранить', save);
for (const field of inputs) {
  field.input.addEventListener('input', validate);
}
el.retryBtn.addEventListener('click', () => {
  haptic.light();
  load();
});
load();
