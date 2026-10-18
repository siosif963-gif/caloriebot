// Общий класс ошибки API: используется и настоящим клиентом (api.js), и демо-режимом (api-demo.js).
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}
