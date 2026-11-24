export async function api(path, method = 'GET', data) {
  const csrf = document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.slice(10);
  const multipart = data instanceof FormData;
  const response = await fetch('/api/' + path + '/', {
    method,
    headers: {...(multipart ? {} : {'Content-Type': 'application/json'}), 'X-CSRFToken': csrf || ''},
    body: data === undefined ? undefined : multipart ? data : JSON.stringify(data),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = result.detail || Object.entries(result).map(([field, messages]) =>
      field.replaceAll('_', ' ') + ': ' + [messages].flat().join(' ')).join(' ');
    throw new Error(message || 'Request failed. Please try again.');
  }
  return result;
}

