// Клиент бэкенда. Все сетевые запросы приложения идут только отсюда.
import { tg } from './app.js';

// Адрес бэкенда. Меняется только здесь.
export const API_BASE_URL = 'https://caloriebot-production-5651.up.railway.app';

const REQUEST_TIMEOUT_MS = 20000;

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request(path, { method = 'GET', body, signal } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (typeof tg.initData === 'string' && tg.initData) {
    headers.Authorization = `tma ${tg.initData}`;
  }

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);

  const onExternalAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener('abort', onExternalAbort, { once: true });
  }

  try {
    let response;
    try {
      response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (err) {
      if (err && err.name === 'AbortError') {
        if (timedOut) {
          throw new ApiError('Сервер не отвечает. Попробуйте ещё раз через минуту.', 0);
        }
        throw err; // отмена внешним сигналом — пробрасываем как есть
      }
      throw new ApiError('Нет соединения с сервером. Проверьте интернет.', 0);
    }

    if (response.status === 204) return null;

    let data = null;
    try {
      data = await response.json();
    } catch (err) {
      if (err && err.name === 'AbortError') {
        if (timedOut) {
          throw new ApiError('Сервер не отвечает. Попробуйте ещё раз через минуту.', 0);
        }
        throw err;
      }
      data = null;
    }

    if (!response.ok) {
      throw new ApiError((data && data.detail) || 'Ошибка сервера', response.status);
    }
    return data;
  } finally {
    clearTimeout(timer);
    if (signal) signal.removeEventListener('abort', onExternalAbort);
  }
}

export function getUser() {
  return request('/api/user/settings');
}

export function updateSettings(data) {
  return request('/api/user/settings', { method: 'PUT', body: data });
}

export function searchProducts(q, signal) {
  return request(`/api/products/search?q=${encodeURIComponent(q)}`, { signal });
}

export function getProduct(id) {
  return request(`/api/products/${encodeURIComponent(id)}`);
}

export function createProduct(data) {
  return request('/api/products', { method: 'POST', body: data });
}

export function deleteProduct(id) {
  return request(`/api/products/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export function addDiaryEntry(data) {
  return request('/api/diary/add', { method: 'POST', body: data });
}

export function getDiaryDay(date) {
  return request(`/api/diary/day?date=${encodeURIComponent(date)}`);
}

export function deleteDiaryEntry(id) {
  return request(`/api/diary/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export function getStats(startDate, endDate) {
  const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
  return request(`/api/stats?${params.toString()}`);
}
