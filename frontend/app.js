// Telegram SDK, навигация, haptic и общие утилиты.

const noop = () => {};

// Заглушка на случай, если скрипт Telegram не загрузился
function createStub() {
  const button = {
    setText: noop, show: noop, hide: noop, onClick: noop, offClick: noop,
    showProgress: noop, hideProgress: noop, enable: noop, disable: noop,
  };
  return {
    initData: '',
    colorScheme: 'light',
    ready: noop,
    expand: noop,
    onEvent: noop,
    offEvent: noop,
    isVersionAtLeast: () => false,
    MainButton: button,
    BackButton: { show: noop, hide: noop, onClick: noop, offClick: noop },
  };
}

export const tg = window.Telegram?.WebApp ?? createStub();
export const isTelegram = typeof tg.initData === 'string' && tg.initData.length > 0;

export const MEAL_TYPES = ['breakfast', 'lunch', 'dinner', 'snack'];
export const MEAL_LABELS = {
  breakfast: 'Завтрак',
  lunch: 'Обед',
  dinner: 'Ужин',
  snack: 'Перекус',
};

// ---------- Haptic ----------

export const haptic = {
  light() {
    tg.HapticFeedback?.impactOccurred?.('light');
  },
  select() {
    tg.HapticFeedback?.selectionChanged?.();
  },
  success() {
    tg.HapticFeedback?.notificationOccurred?.('success');
  },
  error() {
    tg.HapticFeedback?.notificationOccurred?.('error');
  },
};

// ---------- Тема ----------

function applyTheme() {
  document.documentElement.dataset.theme = tg.colorScheme || 'light';
}

// ---------- Запасные кнопки (страница открыта вне Telegram) ----------

let fallbackMain = null;
let fallbackBack = null;
let mainHandler = null;
let backHandler = null;

function ensureFallbackMain() {
  if (!fallbackMain) {
    fallbackMain = document.createElement('button');
    fallbackMain.type = 'button';
    fallbackMain.className = 'fb-main';
    fallbackMain.addEventListener('click', () => {
      if (mainHandler) mainHandler();
    });
    document.body.append(fallbackMain);
  }
  return fallbackMain;
}

function showFallbackBack(onClick) {
  if (!fallbackBack) {
    fallbackBack = document.createElement('button');
    fallbackBack.type = 'button';
    fallbackBack.className = 'fb-back';
    fallbackBack.textContent = '←';
    fallbackBack.setAttribute('aria-label', 'Назад');
    fallbackBack.addEventListener('click', () => {
      if (backHandler) backHandler();
    });
    document.body.append(fallbackBack);
  }
  backHandler = onClick;
  document.body.classList.add('has-fb-back');
}

// ---------- Инициализация ----------

export function initApp({ backTo = null } = {}) {
  tg.ready();
  tg.expand();
  tg.MainButton.hide();
  tg.BackButton.hide();
  applyTheme();
  tg.onEvent('themeChanged', applyTheme);

  if (backTo) {
    const onBack = () => navigate(backTo);
    tg.BackButton.onClick(onBack);
    tg.BackButton.show();
    if (!isTelegram) showFallbackBack(onBack);
  }

  if (document.querySelector('.tabbar')) {
    document.body.classList.add('has-tabbar');
    document.querySelectorAll('.tabbar a').forEach((link) => {
      link.addEventListener('click', () => haptic.light());
    });
  }
}

export function navigate(page, params = {}) {
  haptic.light();
  const query = new URLSearchParams(params).toString();
  location.href = query ? `${page}?${query}` : page;
}

// ---------- MainButton ----------

export function setMainButton(text, onClick) {
  if (mainHandler) tg.MainButton.offClick(mainHandler);
  mainHandler = onClick;
  tg.MainButton.setText(text);
  tg.MainButton.onClick(onClick);
  tg.MainButton.show();
  if (!isTelegram) {
    const button = ensureFallbackMain();
    button.textContent = text;
    button.hidden = false;
  }
}

export function setMainButtonLoading(isLoading) {
  if (isLoading) {
    tg.MainButton.showProgress(false);
    tg.MainButton.disable();
  } else {
    tg.MainButton.hideProgress();
    tg.MainButton.enable();
  }
  if (fallbackMain) fallbackMain.disabled = isLoading;
}

// Включает/выключает MainButton без индикатора загрузки (для валидации форм)
export function setMainButtonEnabled(enabled) {
  if (enabled) tg.MainButton.enable();
  else tg.MainButton.disable();
  if (fallbackMain) fallbackMain.disabled = !enabled;
}

// ---------- Диалоги и тосты ----------

export function confirmDialog(message) {
  return new Promise((resolve) => {
    if (tg.isVersionAtLeast('6.2') && typeof tg.showConfirm === 'function') {
      tg.showConfirm(message, (ok) => resolve(Boolean(ok)));
    } else {
      resolve(window.confirm(message));
    }
  });
}

let toastTimer = null;

export function showToast(message, type = 'info') {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    toast.setAttribute('role', 'status');
    document.body.append(toast);
  }
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, 2500);
}

// ---------- Даты и числа ----------

function pad(n) {
  return String(n).padStart(2, '0');
}

function formatLocalDate(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function parseLocalDate(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(y, m - 1, d);
}

// Сегодняшняя дата по локальному времени (не toISOString — он даёт UTC)
export function todayLocal() {
  return formatLocalDate(new Date());
}

export function addDays(dateStr, n) {
  const date = parseLocalDate(dateStr);
  date.setDate(date.getDate() + n);
  return formatLocalDate(date);
}

export function formatDateRu(dateStr) {
  return parseLocalDate(dateStr).toLocaleDateString('ru-RU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });
}

export function round1(n) {
  return Math.round(n * 10) / 10;
}

// Иконка блюда по ключевым словам названия (порядок важен: частное раньше общего)
const FOOD_ICONS = [
  [/арахис|ореховая паста|паста.*(фундук|шоколад)/, '🥜'],
  [/хот-?дог/, '🌭'],
  [/бургер|воппер|гранд|биг хит|биг спешиал|чикен хит|чикен премьер|биггер|шефбургер|гамбургер/, '🍔'],
  [/пицц|додстер/, '🍕'],
  [/шаурм|твистер|ролл|боксмастер|лонгер|сэндвич|сандвич|сандерс|(^|[^а-яa-z])пита($|[^а-яa-z])|такос|буррито/, '🌯'],
  [/картофель фри|картошка фри|фри$|баскет фри|хашбраун|лук-фри|кранчи/, '🍟'],
  [/наггетс|крыл|стрипс|кусок|ножк|шашлык|байтс|попкорн|курин|кури|грудк|цыпл|индейк/, '🍗'],
  [/мороженое|(^|\s)рожок|пломбир|(^|[^а-яa-z])айс|эскимо/, '🍦'],
  [/пончик|донат/, '🍩'],
  [/печенье|кекс|маффин|пирожок|пирожное|тарталетк|шарлотк/, '🧁'],
  [/торт|чизкейк|медовик|наполеон|эклер|десерт|тирамису|сметанник|фондан|штрудель/, '🍰'],
  [/вафл/, '🧇'],
  [/блин|оладь|сырник/, '🥞'],
  [/шоколад|трюфел|батончик|сникерс|твикс/, '🍫'],
  [/салат|винегрет|оливье|цезарь|капуст/, '🥗'],
  [/суп|борщ|(^|[^а-яa-z])уха($|[^а-яa-z])|окрошк|(^|[^а-яa-z])щи($|[^а-яa-z])|солянк|бульон|похлёбк/, '🍲'],
  [/кофе|капучино|латте|американо|эспрессо|(^|[^а-яa-z])раф($|[^а-яa-z])|глясе|мокко/, '☕'],
  [/чай/, '🍵'],
  [/пиво|сидр|медовуха|глинтвейн|(^|[^а-яa-z])вин[оа]($|[^а-яa-z])/, '🍺'],
  [/(^|[^а-яa-z])кола|кока-кола|пепси|спрайт|фанта|лимонад|морс|(^|[^а-яa-z])сок|квас|напиток|узвар|питень|тархун|коктейль|шейк|мохито|пунш|сбитень|7up|миринда/, '🥤'],
  [/молок|кефир|ряженк|йогурт|сливк|простокваш|сметан|творог/, '🥛'],
  [/сыр|брынз|моцарелл|чоризо/, '🧀'],
  [/яйц|яичн|омлет/, '🍳'],
  [/пельмен|манты|хинкали/, '🥟'],
  [/лук(?!ош)/, '🧅'],
  [/макарон|спагетти|паста|вермишел|карбонар|флотск/, '🍝'],
  [/маслин|оливк/, '🫒'],
  [/хлеб|булочк|батон|тост|гренк|сухар|багет|чиабатт|лаваш|галет/, '🍞'],
  [/гречк|ядриц|манк|пшен|геркулес|цельнозерн|рис|каш|овсян|хлопья|крупа|ризотто|пшён|булгур/, '🍚'],
  [/банан/, '🍌'],
  [/яблок|яблоч/, '🍎'],
  [/апельсин|мандарин/, '🍊'],
  [/груш/, '🍐'],
  [/клубник|клубнич|земляник|малин|ягод|смородин|брусник|черник|вишн|клюкв/, '🍓'],
  [/лимон/, '🍋'],
  [/огур/, '🥒'],
  [/помидор|томат/, '🍅'],
  [/морков/, '🥕'],
  [/картоф|пюре|вареник/, '🥔'],
  [/авокадо/, '🥑'],
  [/кукуруз/, '🌽'],
  [/гриб/, '🍄'],
  [/бекон|ветчин|колбас|сосис|буженин|сардельк/, '🥓'],
  [/говядин|свинин|фарш|котлет|мясо|мясн|тефтел|отбивн|стейк/, '🥩'],
  [/креветк|краб/, '🍤'],
  [/рыб|лосос|сёмг|семг|треск|тунец|форел|сельд|минтай/, '🐟'],
  [/масл/, '🧈'],
  [/(^|\s)мед(\s|$)/, '🍯'],
  [/консерв|горошек/, '🥫'],
  [/орех|миндал|арахис|фундук|кедр/, '🥜'],
  [/соус|кетчуп|майонез|горчиц/, '🥫'],
  [/сахар|карамел|варенье|джем|зефир|конфет/, '🍬'],
  [/фасол|горох|горошек|чечевиц|нут($|[^а-яa-z])|кидни|бобы/, '🫘'],
  [/икра из|икра свекол|кабачк|баклажан/, '🥒'],
  [/рожки|перья|тараллини|ракушк|фузилли|пенне|лапш|вермишел|спагетти|макарон/, '🍝'],
  [/орео|крекер|юбилейн|печень|галет|сушк|баранк|пряник/, '🍪'],
  [/желатин|мармелад|халс|леденец|козинак|жевательн|конфет|драже|ирис/, '🍬'],
  [/кокос/, '🥥'],
  [/цикори/, '☕'],
  [/сайр|горбуш|мойв|шпрот|килька|скумбри|сельд|икра/, '🐟'],
  [/краковск|дымов|сервелат|лопатк|salami|салями|карбонад/, '🥓'],
  [/семеч|подсолнеч/, '🌻'],
  [/изюм|курага|чернослив|виноград|финик|сухофрукт/, '🍇'],
  [/чили|перец|паприк|кайенск/, '🌶️'],
  [/лавров|приправ|специ|соль|пряност/, '🧂'],
  [/хрен|корнишон/, '🥒'],
  [/шампиньон|грибн|гриб/, '🍄'],
  [/даниссимо|данон|творожн|nemoloko|молочн/, '🥛'],
  [/персик|абрикос|нектарин/, '🍑'],
  [/киви/, '🥝'],
  [/гранат|черешн/, '🍒'],
  [/окское|жигулев|балтик|пив/, '🍺'],
  [/байкал|минеральн|(^|[^а-яa-z])вода|воды|компот|нектар/, '🥤'],
  [/чипс|снек|сухарик|попкорн|крекер/, '🍿'],
  [/свр|российск/, '🧀'],
  [/halls|холс|мятн/, '🍬'],
  [/земляничн/, '🍓'],
  [/медвеж.* ушк|ушко|пельмен/, '🥟'],
  [/закуск|закусоч/, '🥫'],
  [/волшебн|сказк/, '🍬'],
];

export function foodEmoji(name) {
  const text = String(name || '').toLowerCase().replace(/ё/g, 'е');
  for (const [pattern, emoji] of FOOD_ICONS) {
    if (pattern.test(text)) return emoji;
  }
  return '🍽️';
}

// Бренд без скобок с алиасами для поиска: «KFC (КФС, Ростикс)» -> «KFC»
export function displayBrand(brand) {
  return String(brand || '').replace(/\s*\(.*\)\s*$/, '').trim();
}

export function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function defaultMealType() {
  const hour = new Date().getHours();
  if (hour < 11) return 'breakfast';
  if (hour <= 15) return 'lunch';
  if (hour <= 20) return 'dinner';
  return 'snack';
}
