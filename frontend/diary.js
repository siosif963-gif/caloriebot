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
} from './app.js';
import { getUser, getDiaryDay, deleteDiaryEntry } from './api.js';

const el = {
  greeting: document.getElementById('greeting'),
  dateLabel: document.getElementById('dateLabel'),
  loading: document.getElementById('loading'),
  errorBox: document.getElementById('errorBox'),
  errorText: document.getElementById('errorText'),
  retryBtn: document.getElementById('retryBtn'),
  content: document.getElementById('content'),
  kcalText: document.getElementById('kcalText'),
  progressFill: document.getElementById('progressFill'),
  kcalCaption: document.getElementById('kcalCaption'),
  macrosLine: document.getElementById('macrosLine'),
  meals: document.getElementById('meals'),
};

const today = todayLocal();

function showState(state) {
  el.loading.hidden = state !== 'loading';
  el.errorBox.hidden = state !== 'error';
  el.content.hidden = state !== 'content';
}

function progressColor(percent) {
  if (percent < 90) return '#34c759';
  if (percent <= 100) return '#ffcc00';
  return '#ff3b30';
}

function renderSummary(day) {
  const eaten = day.totals.calories;
  const goal = day.goals.calories;
  const percent = goal > 0 ? (eaten / goal) * 100 : 0;

  el.kcalText.textContent = `${Math.round(eaten)} / ${Math.round(goal)} ккал`;
  el.progressFill.style.width = `${Math.min(percent, 100)}%`;
  el.progressFill.style.backgroundColor = progressColor(percent);

  const diff = Math.round(goal - eaten);
  el.kcalCaption.textContent =
    diff >= 0 ? `Осталось ${diff} ккал` : `Превышение на ${Math.abs(diff)} ккал`;

  el.macrosLine.textContent =
    `Б ${round1(day.totals.protein)} / ${day.goals.protein}` +
    ` · Ж ${round1(day.totals.fat)} / ${day.goals.fat}` +
    ` · У ${round1(day.totals.carbs)} / ${day.goals.carbs} г`;
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
    brand.textContent = ` ${entry.product_brand}`;
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

  row.append(main, del);
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
