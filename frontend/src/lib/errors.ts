import axios from 'axios';

/**
 * Turn any thrown error (axios/DRF) into a human-readable message.
 * Handles `{detail: "..."}`, field errors `{field: ["..."]}` and plain errors.
 */
export function getErrorMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | Record<string, string | string[] | Record<string, string[]>>
      | undefined;
    if (data) {
      const flat = flattenErrors(data);
      if (flat) return flat;
    }
    if (error.response) return `Request failed (${error.response.status}).`;
    return 'Cannot reach the API. Is the backend running?';
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function flattenErrors(data: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(data)) {
    const label = key === 'non_field_errors' || key === 'detail' ? '' : `${key}: `;
    if (typeof value === 'string') {
      parts.push(`${label}${value}`);
    } else if (Array.isArray(value)) {
      parts.push(`${label}${value.map(String).join(' ')}`);
    } else if (value && typeof value === 'object') {
      const nested = flattenErrors(value as Record<string, unknown>);
      if (nested) parts.push(nested);
    }
  }
  return parts.join(' ');
}
