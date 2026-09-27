export function formatDuration(minutes) {
  if (!Number.isFinite(minutes) || minutes < 0) return "Not available";

  const totalMinutes = Math.round(minutes);
  const hours = Math.floor(totalMinutes / 60);
  const remainingMinutes = totalMinutes % 60;

  if (hours === 0) return `${remainingMinutes} min`;
  const hourLabel = `${hours} hr${hours === 1 ? "" : "s"}`;
  return remainingMinutes ? `${hourLabel} ${remainingMinutes} min` : hourLabel;
}
