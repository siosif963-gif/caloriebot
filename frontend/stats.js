// Экран «Статистика»: линейный график калорий (Chart.js 4) за неделю или месяц.
import { initApp, tg, haptic, todayLocal, addDays, round1 } from './app.js?v=20261013b';
import { getStats } from './api.js?v=20261013b';

const el = {
  periodButtons: document.querySelectorAll('#periodSwitch [data-days]'),
  loading: document.getElementById('loading'),
  errorBox: document.getElementById('errorBox'),
  errorText: document.getElementById('errorText'),
  retryBtn: document.getElementById('retryBtn'),
  emptyState: document.getElementById('emptyState'),
  content: document.getElementById('content'),
  canvas: document.getElementById('chartCanvas'),
  averageLine: document.getElementById('averageLine'),
  statCalories: document.getElementById('statCalories'),
  statProtein: document.getElementById('statProtein'),
  statFat: document.getElementById('statFat'),
  statCarbs: document.getElementById('statCarbs'),
  daysLine: document.getElementById('daysLine'),
};

let periodDays = 7;
let chart = null;
let lastStats = null;
let loadCounter = 0;

function showState(state) {
  el.loading.hidden = state !== 'loading';
  el.errorBox.hidden = state !== 'error';
  el.emptyState.hidden = state !== 'empty';
  el.content.hidden = state !== 'content';
}

function cssColor(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function themeColors() {
  return {
    text: cssColor('--tg-theme-text-color', cssColor('--text', '#000000')),
    hint: cssColor('--tg-theme-hint-color', cssColor('--hint', '#8e8e93')),
    button: cssColor('--tg-theme-button-color', cssColor('--btn', '#2481cc')),
    grid: 'rgba(127, 127, 127, 0.25)',
  };
}

// Полупрозрачная заливка: поддерживаем #rrggbb, иначе возвращаем цвет как есть
function withAlpha(color, alpha) {
  const m = /^#([0-9a-f]{6})$/i.exec(color);
  if (!m) return color;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function formatLabel(dateStr) {
  const [, month, day] = dateStr.split('-');
  return `${day}.${month}`;
}

function drawChart() {
  if (!lastStats || typeof Chart === 'undefined') return;
  if (chart) {
    chart.destroy();
    chart = null;
  }
  const colors = themeColors();
  const labels = lastStats.days.map((d) => formatLabel(d.date));

  chart = new Chart(el.canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Калории',
          data: lastStats.days.map((d) => d.calories),
          borderColor: colors.button,
          backgroundColor: withAlpha(colors.button, 0.14),
          fill: true,
          borderWidth: 3,
          pointRadius: 3,
          pointBackgroundColor: colors.button,
          tension: 0.3,
        },
        {
          label: 'Норма',
          data: lastStats.days.map(() => lastStats.goal_calories),
          borderColor: colors.hint,
          backgroundColor: colors.hint,
          borderWidth: 2,
          borderDash: [6, 4],
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { labels: { color: colors.text, usePointStyle: true, boxWidth: 8, boxHeight: 8 } },
      },
      scales: {
        x: {
          ticks: { color: colors.hint, maxRotation: 0, autoSkip: true },
          grid: { color: colors.grid },
        },
        y: {
          beginAtZero: true,
          ticks: { color: colors.hint },
          grid: { color: colors.grid },
        },
      },
    },
  });
}

function render(stats) {
  lastStats = stats;
  if (stats.days_logged === 0) {
    if (chart) {
      chart.destroy();
      chart = null;
    }
    showState('empty');
    return;
  }
  const avg = stats.averages;
  el.statCalories.textContent = String(Math.round(avg.calories));
  el.statProtein.textContent = String(Math.round(avg.protein));
  el.statFat.textContent = String(Math.round(avg.fat));
  el.statCarbs.textContent = String(Math.round(avg.carbs));
  el.averageLine.textContent =
    `В среднем: ${Math.round(avg.calories)} ккал · Б ${round1(avg.protein)}` +
    ` · Ж ${round1(avg.fat)} · У ${round1(avg.carbs)}`;
  el.daysLine.textContent = `Дней с записями: ${stats.days_logged} из ${stats.days.length}`;
  showState('content');
  drawChart();
}

async function load() {
  loadCounter += 1;
  const myLoad = loadCounter;
  showState('loading');
  const end = todayLocal();
  const start = addDays(end, -(periodDays - 1));
  try {
    const stats = await getStats(start, end);
    if (myLoad !== loadCounter) return;
    render(stats);
  } catch (err) {
    if (myLoad !== loadCounter) return;
    el.errorText.textContent = err.message || 'Не удалось загрузить статистику';
    showState('error');
  }
}

initApp();

el.periodButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const days = Number(button.dataset.days);
    if (days === periodDays) return;
    haptic.select();
    periodDays = days;
    el.periodButtons.forEach((b) => b.classList.toggle('active', b === button));
    load();
  });
});
el.retryBtn.addEventListener('click', () => {
  haptic.light();
  load();
});
tg.onEvent('themeChanged', drawChart);

load();
