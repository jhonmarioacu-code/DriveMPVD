import { afterEach, describe, expect, it, vi } from "vitest";

import { createProgressReporter } from "./progress-reporter";

describe("createProgressReporter", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("emits immediately and coalesces later progress to the newest value", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-19T00:00:00Z"));
    const onProgress = vi.fn();
    const reporter = createProgressReporter(onProgress, 100);

    reporter.report(10);
    reporter.report(20);
    reporter.report(30);

    expect(onProgress).toHaveBeenCalledExactlyOnceWith(10);
    vi.advanceTimersByTime(99);
    expect(onProgress).toHaveBeenCalledExactlyOnceWith(10);
    vi.advanceTimersByTime(1);
    expect(onProgress).toHaveBeenLastCalledWith(30);
    expect(onProgress).toHaveBeenCalledTimes(2);
  });

  it("flushes a pending value and cancels future updates", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-19T00:00:00Z"));
    const onProgress = vi.fn();
    const reporter = createProgressReporter(onProgress, 100);

    reporter.report(10);
    reporter.report(20);
    reporter.flush();
    reporter.report(30);
    reporter.cancel();
    vi.advanceTimersByTime(100);

    expect(onProgress.mock.calls).toEqual([10, 20].map((value) => [value]));
  });
});
