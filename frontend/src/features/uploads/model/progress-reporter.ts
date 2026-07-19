const DEFAULT_INTERVAL_MS = 100;

export interface ProgressReporter {
  cancel(): void;
  flush(): void;
  report(uploadedBytes: number): void;
}

/** Limit upload UI updates while preserving the most recent byte count. */
export function createProgressReporter(
  onProgress: (uploadedBytes: number) => void,
  intervalMs = DEFAULT_INTERVAL_MS,
): ProgressReporter {
  let lastReportedAt = Number.NEGATIVE_INFINITY;
  let latest: number | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let cancelled = false;

  const flush = () => {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
    if (latest === null || cancelled) return;
    const value = latest;
    latest = null;
    lastReportedAt = Date.now();
    onProgress(value);
  };

  return {
    report(uploadedBytes) {
      if (cancelled) return;
      latest = uploadedBytes;
      const dueIn = Math.max(0, lastReportedAt + intervalMs - Date.now());
      if (dueIn === 0) {
        flush();
      } else {
        timer ??= setTimeout(flush, dueIn);
      }
    },
    flush,
    cancel() {
      cancelled = true;
      latest = null;
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
    },
  };
}
