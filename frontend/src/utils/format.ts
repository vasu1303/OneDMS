export const formatDateTime = (value: string | null | undefined): string => {
  if (!value) {
    return '—';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
};

export const formatMoney = (value: number, currency: string): string => {
  if (!currency) return `${value.toLocaleString('en-IN')} (currency missing)`;
  try {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 }).format(value);
  } catch {
    return `${value.toLocaleString('en-IN')} (${currency})`;
  }
};

export const parseRouteId = (value?: string): number =>
  value && /^[1-9]\d*$/.test(value) && Number.isSafeInteger(Number(value)) ? Number(value) : NaN;

export const statusLabel = (value: string): string => {
  const label = value.replaceAll('_', ' ');
  return label.charAt(0).toUpperCase() + label.slice(1);
};

export const severityRank = (severity: 'error' | 'warning' | 'info'): number => {
  if (severity === 'error') {
    return 0;
  }

  if (severity === 'warning') {
    return 1;
  }

  return 2;
};
