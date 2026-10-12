// Экран «Дневник»: прогресс калорий и записи по приёмам пищи.
import {
  initApp,
  setMainButton,
  navigate,
  confirmDialog,
  haptic,
  showToast,
  todayLocal,
  formatDateRu,
  round1,
  MEAL_TYPES,
  MEAL_LABELS,
  displayBrand,
  foodEmoji,
} from './app.js?v=20261013c';
import { getUser, getDiaryDay, deleteDiaryEntry } from './api.js?v=20261013c';

const el = {
  greeting: document.getElementById('greeting'),
  dateLabel: document.getElementById('dateLabel'),
  loading: document.getElementById('loading'),
  errorBox: document.getElementById('errorBox'),
  errorText: document.getElementById('errorText'),
  retryBtn: document.getElementById('retryBtn'),
  content: document.getElementById('content'),
  kcalText: document.getElementById('kcalText'),
  ringValue: document.getElementById('ringValue'),
  ringFill: document.getElementById('ringFill'),
  kcalCaption: document.getElementById('kcalCaption'),
  meals: document.getElementById('meals'),
};

const today = todayLocal();

function showState(state) {
  el.loading.hidden = state !== 'loading';
  el.errorBox.hidden = state !== 'error';
  el.content.hidden = state !== 'content';
}

const RING_LENGTH = 2 * Math.PI * 52;

function progressColor(percent) {
  if (percent < 90) return '#30c25d';
  if (percent <= 100) return '#f5b800';
  return '#ff4d43';
}

function setMacro(name, eaten, goal) {
  const percent = goal > 0 ? (eaten / goal) * 100 : 0;
  document.getElementById(`${name}Text`).textContent = `${Math.round(eaten)} / ${goal} г`;
  document.getElementById(`${name}Fill`).style.width = `${Math.min(percent, 100)}%`;
}

function renderSummary(day) {
  const eaten = day.totals.calories;
  const goal = day.goals.calories;
  const percent = goal > 0 ? (eaten / goal) * 100 : 0;

  el.ringValue.textContent = String(Math.round(eaten));
  el.ringFill.style.strokeDasharray = String(RING_LENGTH);
  el.ringFill.style.strokeDashoffset = String(RING_LENGTH * (1 - Math.min(percent, 100) / 100));
  el.ringFill.style.stroke = progressColor(percent);

  el.kcalText.textContent = `${Math.round(eaten)} / ${Math.round(goal)} ккал`;
  const diff = Math.round(goal - eaten);
  el.kcalCaption.textContent =
    diff >= 0 ? `Осталось ${diff} ккал` : `Превышение на ${Math.abs(diff)} ккал`;

  setMacro('protein', day.totals.protein, day.goals.protein);
  setMacro('fat', day.totals.fat, day.goals.fat);
  setMacro('carbs', day.totals.carbs, day.goals.carbs);
}

function renderEntry(entry) {
  const row = document.createElement('div');
  row.className = 'entry';

  const main = document.createElement('div');
  main.className = 'entry-main';

  const name = document.createElement('div');
  name.className = 'entry-name';
  name.textContent = entry.product_name;
  if (entry.product_brand) {
    const brand = document.createElement('span');
    brand.className = 'entry-brand';
    brand.textContent = ` ${displayBrand(entry.product_brand)}`;
    name.append(brand);
  }

  const meta = document.createElement('div');
  meta.className = 'entry-meta';
  meta.textContent = `${round1(entry.weight_g)} г · ${round1(entry.calories)} ккал`;

  main.append(name, meta);

  const del = document.createElement('button');
  del.type = 'button';
  del.className = 'icon-btn';
  del.textContent = '×';
  del.setAttribute('aria-label', `Удалить «${entry.product_name}»`);
  del.addEventListener('click', () => onDelete(entry));

  const icon = document.createElement('div');
  icon.className = 'entry-icon';
  icon.textContent = foodEmoji(entry.product_name);

  row.append(icon, main, del);
  return row;
}

function renderMeals(day) {
  el.meals.replaceChildren();
  for (const meal of MEAL_TYPES) {
    const block = document.createElement('section');
    block.className = 'card meal-card';
    block.dataset.meal = meal;

    const head = document.createElement('div');
    head.className = 'meal-head';
    const title = document.createElement('h2');
    title.textContent = MEAL_LABELS[meal];
    const sum = document.createElement('span');
    sum.className = 'hint';
    sum.textContent = `${Math.round(day.meal_totals[meal].calories)} ккал`;
    head.append(title, sum);
    block.append(head);

    const entries = day.meals[meal] || [];
    if (entries.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'meal-empty';
      empty.textContent = 'Пока пусто';
      block.append(empty);
    } else {
      entries.forEach((entry) => block.append(renderEntry(entry)));
    }
    el.meals.append(block);
  }
}

async function onDelete(entry) {
  haptic.light();
  const ok = await confirmDialog(`Удалить «${entry.product_name}»?`);
  if (!ok) return;
  try {
    await deleteDiaryEntry(entry.id);
    haptic.success();
    await load();
  } catch (err) {
    haptic.error();
    showToast(err.message || 'Не удалось удалить запись', 'error');
  }
}

async function load() {
  showState('loading');
  try {
    const [user, day] = await Promise.all([getUser(), getDiaryDay(today)]);
    el.greeting.textContent = user.first_name ? `Привет, ${user.first_name}!` : 'Привет!';
    el.dateLabel.textContent = formatDateRu(today);
    renderSummary(day);
    renderMeals(day);
    showState('content');
  } catch (err) {
    el.errorText.textContent = err.message || 'Не удалось загрузить дневник';
    showState('error');
  }
}

initApp();
el.dateLabel.textContent = formatDateRu(today);
setMainButton('Добавить продукт', () => navigate('search.html'));
el.retryBtn.addEventListener('click', () => {
  haptic.light();
  load();
});
load();
