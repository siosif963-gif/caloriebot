// Демо-режим: те же функции и форматы ответов, что у api.js, но без сервера.
// Продукты берутся из встроенной базы (data/products.json), дневник, свои продукты и нормы
// хранятся в localStorage этого браузера. Модуль не делает ничего при импорте.
import { ApiError } from './errors.js?v=20261019a';

const VERSION = '20261019a';
const STORAGE_KEY = 'caloriebot.demo.v1';
const MODE_KEY = 'caloriebot.demo.mode';
const MAX_USER_PRODUCTS = 300;
const USER_PRODUCT_ID_BASE = 1000000;
const MEAL_TYPES = ['breakfast', 'lunch', 'dinner', 'snack'];
const MACRO_KEYS = ['calories', 'protein', 'fat', 'carbs'];
const MAX_RESULTS = 20;

// ---------- Включён ли демо-режим ----------

let demoCache = null;

// Демо — только вне Telegram. Внутри Telegram (есть initData) всегда настоящий бэкенд,
// даже с ?demo=1. Вне Telegram можно отключить демо параметром ?demo=0 (для разработки).
export function isDemoMode() {
  if (demoCache !== null) return demoCache;
  const initData = window.Telegram?.WebApp?.initData;
  if (typeof initData === 'string' && initData.length > 0) {
    demoCache = false;
    return demoCache;
  }
  let flag = new URLSearchParams(location.search).get('demo');
  try {
    if (flag !== null) sessionStorage.setItem(MODE_KEY, flag);
    else flag = sessionStorage.getItem(MODE_KEY);
  } catch {
    // sessionStorage недоступен — берём только параметр адреса
  }
  demoCache = flag !== '0';
  return demoCache;
}

// ---------- Хранилище: localStorage, запасной вариант — window.name, иначе память ----------

function storageRead() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return raw;
  } catch {
    // localStorage недоступен
  }
  try {
    if (window.name.startsWith(`${STORAGE_KEY}=`)) return window.name.slice(STORAGE_KEY.length + 1);
  } catch {
    // window.name недоступен
  }
  return null;
}

function storageWrite(raw) {
  let saved = false;
  try {
    localStorage.setItem(STORAGE_KEY, raw);
    saved = true;
  } catch {
    // localStorage недоступен или переполнен
  }
  if (!saved) {
    try {
      window.name = `${STORAGE_KEY}=${raw}`;
    } catch {
      // остаёмся только в памяти текущей страницы
    }
  }
}

function storageClear() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // нечего очищать
  }
  try {
    if (window.name.startsWith(`${STORAGE_KEY}=`)) window.name = '';
  } catch {
    // нечего очищать
  }
}

// ---------- Утилиты ----------

const pad = (n) => String(n).padStart(2, '0');
const round1 = (n) => Math.round(n * 10) / 10;

function formatLocalDate(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function parseLocalDate(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function addDays(dateStr, n) {
  const date = parseLocalDate(dateStr);
  date.setDate(date.getDate() + n);
  return formatLocalDate(date);
}

const todayStr = () => formatLocalDate(new Date());

function daysBetween(fromStr, toStr) {
  return Math.round((parseLocalDate(toStr) - parseLocalDate(fromStr)) / 86400000);
}

function isValidDateStr(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  return formatLocalDate(parseLocalDate(value)) === value;
}

// Та же нормализация, что в product_service.normalize_name на бэкенде
function normalizeName(...parts) {
  const text = parts.filter(Boolean).join(' ').toLowerCase().replace(/ё/g, 'е');
  return text.replace(/[^\p{L}\p{N}_\s%]/gu, ' ').replace(/\s+/g, ' ').trim();
}

function fail(field, reason, status = 422) {
  return new ApiError(`Некорректные данные: ${field} — ${reason}`, status);
}

function abortIfNeeded(signal) {
  if (signal && signal.aborted) throw new DOMException('Aborted', 'AbortError');
}

// ---------- Встроенная база продуктов ----------

let catalogPromise = null;

function loadCatalog() {
  if (!catalogPromise) {
    const url = new URL(`./data/products.json?v=${VERSION}`, import.meta.url);
    catalogPromise = fetch(url)
      .then((response) => {
        if (!response.ok) throw new Error(String(response.status));
        return response.json();
      })
      .then((data) =>
        data.items.map((row, index) => ({
          id: index + 1,
          code: row[0],
          name: row[1],
          brand: row[2] || null,
          calories: row[3],
          protein: row[4],
          fat: row[5],
          carbs: row[6],
          image_url: row[7] || null,
          source: 'local',
          name_search: normalizeName(row[1], row[2]),
        })),
      )
      .catch(() => {
        catalogPromise = null;
        throw new ApiError('Не удалось загрузить встроенную базу продуктов.', 0);
      });
  }
  return catalogPromise;
}

// Штрихкод продукта из выгрузки OpenFoodFacts: код вида off-<штрихкод> или st-<штрихкод>
function barcodeOf(product) {
  const match = /^(?:off|st)-(\d{8,14})$/.exec(product.code);
  return match ? match[1] : null;
}

function publicProduct(product) {
  return {
    id: product.id,
    code: product.code,
    name: product.name,
    brand: product.brand,
    calories: product.calories,
    protein: product.protein,
    fat: product.fat,
    carbs: product.carbs,
    image_url: product.image_url,
    source: product.source,
  };
}

// ---------- Состояние демо ----------

// Демо-данные: [название, подсказка по бренду (null — продукт без бренда), вес, приём пищи].
// Нужный продукт ищется во встроенной базе; если его нет — запись пропускается.
const SEED_DAYS = [
  [ // сегодня
    ['Овсяные хлопья', 'ВкусВилл', 70, 'breakfast'], ['Банан', null, 110, 'breakfast'],
    ['Молоко 2.5%', 'Простоквашино', 200, 'breakfast'],
    ['Куриная грудка варёная', null, 180, 'lunch'], ['Гречка варёная', null, 200, 'lunch'],
    ['Салат Цезарь', 'Вкусно', 150, 'lunch'],
    ['Лосось', null, 150, 'dinner'], ['Картофель варёный', null, 200, 'dinner'],
    ['Творог 5%', 'ВкусВилл', 150, 'snack'],
  ],
  [ // вчера
    ['Яйцо куриное варёное', null, 110, 'breakfast'], ['Хлеб ржаной', null, 60, 'breakfast'],
    ['Борщ с Рубленым Мясом', 'Теремок', 350, 'lunch'], ['Хлеб ржаной', null, 40, 'lunch'],
    ['Макароны варёные', null, 250, 'dinner'], ['Говядина варёная', null, 120, 'dinner'],
    ['Яблоко', null, 180, 'snack'],
  ],
  [
    ['Овсяная каша на воде', null, 250, 'breakfast'], ['Банан', null, 100, 'breakfast'],
    ['Шаурма куриная', null, 300, 'lunch'],
    ['Рис белый варёный', null, 220, 'dinner'], ['Треска', null, 180, 'dinner'], ['Огурец', null, 100, 'dinner'],
    ['Миндаль', null, 30, 'snack'],
  ],
  [
    ['Творог 5%', 'ВкусВилл', 200, 'breakfast'], ['Мёд', null, 20, 'breakfast'],
    ['Куриная грудка варёная', null, 200, 'lunch'], ['Гречка варёная', null, 250, 'lunch'],
    ['Пицца Пепперони', 'Zotman', 250, 'dinner'],
    ['Яблоко', null, 200, 'snack'],
  ],
  [
    ['Сырники', 'ВкусВилл', 180, 'breakfast'], ['Йогурт натуральный 3.5%', 'ВкусВилл', 125, 'breakfast'],
    ['Пельмени', 'Теремок', 250, 'lunch'],
    ['Лосось', null, 150, 'dinner'], ['Помидор', null, 150, 'dinner'], ['Огурец', null, 100, 'dinner'],
    ['Шоколад молочный', null, 25, 'snack'],
  ],
  [
    ['Кефир 1%', null, 250, 'breakfast'], ['Овсяные хлопья', 'ВкусВилл', 60, 'breakfast'],
    ['Чикен Хит', 'Вкусно', 198, 'lunch'], ['Картофель фри', 'Вкусно', 110, 'lunch'],
    ['Салат Цезарь', 'Вкусно', 200, 'dinner'], ['Куриная грудка варёная', null, 150, 'dinner'],
    ['Банан', null, 120, 'snack'],
  ],
  [
    ['Яйцо куриное варёное', null, 110, 'breakfast'], ['Хлеб ржаной', null, 70, 'breakfast'],
    ['Авокадо', null, 60, 'breakfast'],
    ['Борщ Постный с Булочкой', 'Теремок', 350, 'lunch'],
    ['Гречка варёная', null, 200, 'dinner'], ['Говядина варёная', null, 130, 'dinner'],
    ['Морковь', null, 100, 'dinner'],
    ['Миндаль', null, 30, 'snack'],
  ],
];

const MEAL_TIMES = { breakfast: 8 * 60 + 15, lunch: 13 * 60 + 10, dinner: 19 * 60 + 20, snack: 16 * 60 + 30 };

function makeEntry(id, product, weight, meal, date, minutes) {
  const time = `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}:00`;
  return {
    id,
    product_id: product.id,
    product_name: product.name,
    product_brand: product.brand,
    meal_type: meal,
    weight_g: weight,
    calories: round1((product.calories * weight) / 100),
    protein: round1((product.protein * weight) / 100),
    fat: round1((product.fat * weight) / 100),
    carbs: round1((product.carbs * weight) / 100),
    entry_date: date,
    created_at: `${date}T${time}Z`,
    seed: false,
  };
}

function buildSeedState(catalog) {
  const today = todayStr();
  const state = {
    version: 1,
    seedDate: today,
    user: {
      telegram_id: 1,
      first_name: 'Гость',
      username: null,
      daily_calories: 2000,
      daily_protein: 100,
      daily_fat: 67,
      daily_carbs: 250,
    },
    products: [],
    entries: [],
    nextEntryId: 1,
    nextProductId: USER_PRODUCT_ID_BASE,
  };
  SEED_DAYS.forEach((items, offset) => {
    const date = addDays(today, -offset);
    const counters = {};
    items.forEach(([name, brandHint, weight, meal]) => {
      const product = catalog.find(
        (p) =>
          p.name === name &&
          (brandHint === null ? !p.brand : p.brand && p.brand.includes(brandHint)),
      );
      if (!product) return;
      counters[meal] = (counters[meal] || 0) + 1;
      const entry = makeEntry(
        state.nextEntryId,
        product,
        weight,
        meal,
        date,
        MEAL_TIMES[meal] + counters[meal] * 3,
      );
      entry.seed = true;
      state.entries.push(entry);
      state.nextEntryId += 1;
    });
  });
  return state;
}

function isValidState(state) {
  return (
    state &&
    state.version === 1 &&
    state.user &&
    Array.isArray(state.entries) &&
    Array.isArray(state.products) &&
    Number.isInteger(state.nextEntryId) &&
    Number.isInteger(state.nextProductId)
  );
}

let state = null;
let statePromise = null;

function saveState() {
  storageWrite(JSON.stringify(state));
}

// Демо-записи «едут» вместе с датой: сколько дней прошло с последнего визита, на столько
// сдвигаем сид, чтобы неделя статистики не пустела. Записи пользователя не трогаем.
function rollSeedForward(current) {
  const today = todayStr();
  const delta = daysBetween(current.seedDate || today, today);
  if (delta > 0) {
    current.entries.forEach((entry) => {
      if (!entry.seed) return;
      entry.entry_date = addDays(entry.entry_date, delta);
      entry.created_at = `${entry.entry_date}${entry.created_at.slice(10)}`;
    });
  }
  current.seedDate = today;
}

function ready() {
  if (!statePromise) {
    statePromise = loadCatalog().then((catalog) => {
      let loaded = null;
      try {
        const raw = storageRead();
        loaded = raw ? JSON.parse(raw) : null;
      } catch {
        loaded = null;
      }
      if (isValidState(loaded)) {
        state = loaded;
        rollSeedForward(state);
      } else {
        state = buildSeedState(catalog);
      }
      saveState();
      return catalog;
    });
    statePromise.catch(() => {
      statePromise = null;
    });
  }
  return statePromise;
}

function findProduct(catalog, id) {
  if (id >= USER_PRODUCT_ID_BASE) return state.products.find((p) => p.id === id) || null;
  return catalog[id - 1] || null;
}

// ---------- Сброс демо и плашка ----------

export function resetDemo() {
  storageClear();
  state = null;
  statePromise = null;
  location.reload();
}

export function mountDemoBanner() {
  if (document.getElementById('demoBar')) return;
  const bar = document.createElement('div');
  bar.id = 'demoBar';
  bar.className = 'demo-bar';

  const text = document.createElement('span');
  text.textContent = 'Демо-режим: данные хранятся только в вашем браузере';

  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Сбросить демо';
  button.addEventListener('click', () => {
    if (window.confirm('Удалить все данные демо и начать заново?')) resetDemo();
  });

  bar.append(text, button);
  document.body.prepend(bar);
  document.body.classList.add('has-demo-bar');
}

// ---------- API: те же функции, что в api.js ----------

export async function getUser() {
  await ready();
  return { ...state.user };
}

export async function updateSettings(data) {
  await ready();
  const rules = [
    ['daily_calories', 800, 10000],
    ['daily_protein', 0, 500],
    ['daily_fat', 0, 500],
    ['daily_carbs', 0, 1000],
  ];
  for (const [key, min, max] of rules) {
    const value = data?.[key];
    if (!Number.isInteger(value) || value < min || value > max) {
      throw fail(key, `значение должно быть целым числом от ${min} до ${max}`);
    }
  }
  for (const [key] of rules) state.user[key] = data[key];
  saveState();
  return { ...state.user };
}

export async function searchProducts(q, signal) {
  abortIfNeeded(signal);
  const catalog = await ready();
  abortIfNeeded(signal);

  const query = String(q ?? '').trim();
  if (query.length < 2 || query.length > 100) {
    throw fail('q', 'длина запроса от 2 до 100 символов');
  }

  if (/^\d{8,14}$/.test(query)) {
    const found = catalog.find((p) => barcodeOf(p) === query);
    return { items: found ? [publicProduct(found)] : [], external_status: 'skipped' };
  }

  const words = normalizeName(query).split(' ').filter(Boolean).slice(0, 5);
  if (words.length === 0) return { items: [], external_status: 'skipped' };

  const own = state.products.map((p) => ({ ...p, name_search: normalizeName(p.name, p.brand) }));
  const rank = (p) => (p.source === 'user' ? 0 : p.code.startsWith('off-') ? 2 : 1);
  const matches = [...own, ...catalog]
    .filter((p) => words.every((word) => p.name_search.includes(word)))
    .sort((a, b) => rank(a) - rank(b) || a.name.length - b.name.length);

  // Один и тот же продукт не показываем дважды (как на бэкенде — по поисковой строке)
  const unique = new Map();
  for (const product of matches) {
    if (!unique.has(product.name_search)) unique.set(product.name_search, product);
  }
  const items = [...unique.values()].slice(0, MAX_RESULTS).map(publicProduct);
  return { items, external_status: 'skipped' };
}

export async function getProduct(id) {
  const catalog = await ready();
  const product = findProduct(catalog, Number(id));
  if (!product) throw new ApiError('Продукт не найден', 404);
  return publicProduct(product);
}

export async function createProduct(data) {
  await ready();
  const name = String(data?.name ?? '').split(/\s+/).filter(Boolean).join(' ');
  const brand = String(data?.brand ?? '').split(/\s+/).filter(Boolean).join(' ') || null;
  if (name.length < 2 || name.length > 100) throw fail('name', 'название от 2 до 100 символов');
  if (brand && brand.length > 100) throw fail('brand', 'бренд не длиннее 100 символов');

  const limits = { calories: 900, protein: 100, fat: 100, carbs: 100 };
  for (const key of MACRO_KEYS) {
    const value = data[key];
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > limits[key]) {
      throw fail(key, `значение должно быть от 0 до ${limits[key]}`);
    }
  }
  if (data.protein + data.fat + data.carbs > 100.0001) {
    throw fail(
      'запрос',
      'сумма белков, жиров и углеводов не может быть больше 100 г на 100 г продукта',
    );
  }
  if (state.products.length >= MAX_USER_PRODUCTS) {
    throw new ApiError(`Можно создать не больше ${MAX_USER_PRODUCTS} своих продуктов`, 422);
  }

  state.nextProductId += 1;
  const product = {
    id: state.nextProductId,
    code: `u-${Date.now().toString(16)}${state.nextProductId}`,
    name,
    brand,
    calories: round1(data.calories),
    protein: round1(data.protein),
    fat: round1(data.fat),
    carbs: round1(data.carbs),
    image_url: null,
    source: 'user',
  };
  state.products.push(product);
  saveState();
  return publicProduct(product);
}

export async function deleteProduct(id) {
  await ready();
  const index = state.products.findIndex((p) => p.id === Number(id));
  if (index === -1) throw new ApiError('Продукт не найден', 404);
  const [removed] = state.products.splice(index, 1);
  // Записи дневника остаются со снимком названия и КБЖУ, связь с продуктом обнуляется
  state.entries.forEach((entry) => {
    if (entry.product_id === removed.id) entry.product_id = null;
  });
  saveState();
  return null;
}

function publicEntry(entry) {
  const { seed, ...rest } = entry; // eslint-disable-line no-unused-vars
  return rest;
}

export async function addDiaryEntry(data) {
  const catalog = await ready();
  if (!Number.isInteger(data?.product_id) || data.product_id <= 0) {
    throw fail('product_id', 'должен быть положительным числом');
  }
  const weight = data.weight_g;
  if (typeof weight !== 'number' || !Number.isFinite(weight) || weight < 1 || weight > 5000) {
    throw fail('weight_g', 'вес должен быть от 1 до 5000 г');
  }
  if (!MEAL_TYPES.includes(data.meal_type)) {
    throw fail('meal_type', 'приём пищи: breakfast, lunch, dinner или snack');
  }
  const today = todayStr();
  if (
    !isValidDateStr(data.entry_date) ||
    data.entry_date < addDays(today, -365) ||
    data.entry_date > addDays(today, 1)
  ) {
    throw fail('entry_date', 'дата должна быть не старше 365 дней и не позже завтрашней');
  }
  const product = findProduct(catalog, data.product_id);
  if (!product) throw new ApiError('Продукт не найден', 404);

  const now = new Date();
  const entry = makeEntry(
    state.nextEntryId,
    product,
    weight,
    data.meal_type,
    data.entry_date,
    now.getHours() * 60 + now.getMinutes(),
  );
  entry.created_at = now.toISOString().replace(/\.\d{3}Z$/, 'Z');
  state.nextEntryId += 1;
  state.entries.push(entry);
  saveState();
  return publicEntry(entry);
}

const zeroTotals = () => ({ calories: 0, protein: 0, fat: 0, carbs: 0 });

function roundTotals(totals) {
  return Object.fromEntries(MACRO_KEYS.map((key) => [key, round1(totals[key])]));
}

export async function getDiaryDay(date) {
  await ready();
  if (!isValidDateStr(date)) throw fail('date', 'ожидается дата в формате ГГГГ-ММ-ДД');

  const meals = Object.fromEntries(MEAL_TYPES.map((meal) => [meal, []]));
  const mealTotals = Object.fromEntries(MEAL_TYPES.map((meal) => [meal, zeroTotals()]));
  const totals = zeroTotals();

  const dayEntries = state.entries
    .filter((entry) => entry.entry_date === date)
    .sort((a, b) => (a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : a.id - b.id));
  for (const entry of dayEntries) {
    const meal = MEAL_TYPES.includes(entry.meal_type) ? entry.meal_type : 'snack';
    meals[meal].push(publicEntry(entry));
    for (const key of MACRO_KEYS) {
      mealTotals[meal][key] += entry[key];
      totals[key] += entry[key];
    }
  }

  return {
    date,
    meals,
    meal_totals: Object.fromEntries(MEAL_TYPES.map((meal) => [meal, roundTotals(mealTotals[meal])])),
    totals: roundTotals(totals),
    goals: {
      calories: state.user.daily_calories,
      protein: state.user.daily_protein,
      fat: state.user.daily_fat,
      carbs: state.user.daily_carbs,
    },
  };
}

export async function deleteDiaryEntry(id) {
  await ready();
  const index = state.entries.findIndex((entry) => entry.id === Number(id));
  if (index === -1) throw new ApiError('Запись не найдена', 404);
  state.entries.splice(index, 1);
  saveState();
  return null;
}

export async function getStats(startDate, endDate) {
  await ready();
  if (!isValidDateStr(startDate)) throw fail('start_date', 'ожидается дата в формате ГГГГ-ММ-ДД');
  if (!isValidDateStr(endDate)) throw fail('end_date', 'ожидается дата в формате ГГГГ-ММ-ДД');
  if (endDate < startDate) throw fail('end_date', 'не может быть раньше start_date');
  const periodDays = daysBetween(startDate, endDate) + 1;
  if (periodDays > 31) throw fail('end_date', 'период не может быть длиннее 31 дня');

  const byDate = new Map();
  for (const entry of state.entries) {
    if (entry.entry_date < startDate || entry.entry_date > endDate) continue;
    const sums = byDate.get(entry.entry_date) || zeroTotals();
    for (const key of MACRO_KEYS) sums[key] += entry[key];
    byDate.set(entry.entry_date, sums);
  }

  const days = [];
  for (let offset = 0; offset < periodDays; offset += 1) {
    const date = addDays(startDate, offset);
    days.push({ date, ...roundTotals(byDate.get(date) || zeroTotals()) });
  }

  const daysLogged = byDate.size;
  const averages = zeroTotals();
  if (daysLogged > 0) {
    for (const key of MACRO_KEYS) {
      let sum = 0;
      byDate.forEach((sums) => {
        sum += sums[key];
      });
      averages[key] = round1(sum / daysLogged);
    }
  }

  return {
    start_date: startDate,
    end_date: endDate,
    days,
    averages,
    days_logged: daysLogged,
    goal_calories: state.user.daily_calories,
  };
}
