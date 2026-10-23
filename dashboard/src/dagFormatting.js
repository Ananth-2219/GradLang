export function formatDagValue(value) {
  if (value === null || value === undefined) return 'Not evaluated';
  return Number.isFinite(value) ? String(Number(value.toPrecision(6))) : String(value);
}
