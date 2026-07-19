export function formatUploadBytes(value: number) {
  if (value <= 0) return "0 B";

  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(
    Math.floor(Math.log(value) / Math.log(1024)),
    units.length - 1,
  );
  const scaled = value / 1024 ** index;

  return `${new Intl.NumberFormat("es", {
    maximumFractionDigits: index === 0 ? 0 : 1,
  }).format(scaled)} ${units[index] ?? "B"}`;
}

export function uploadProgressPercentage(uploadedBytes: number, totalBytes: number) {
  if (totalBytes === 0) return 100;
  return Math.round(Math.min(100, Math.max(0, (uploadedBytes / totalBytes) * 100)));
}
