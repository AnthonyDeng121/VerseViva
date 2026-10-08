import { describe, expect, it } from "vitest";

import {
  calculateTimelinePlacement,
  canTransitionRecorder,
  normalizeLoopTime,
  offsetFromDrag,
} from "./audioTimeline";

describe("shared audio timeline", () => {
  it("moves a take earlier for a positive correction", () => {
    const placement = calculateTimelinePlacement({
      timelineStartSeconds: 12,
      latencyCompensationMs: 100,
      manualOffsetMs: 200,
      rangeStartSeconds: 10,
      rangeDurationSeconds: 5,
      bufferDurationSeconds: 4,
    });
    expect(placement.clipStartSeconds).toBeCloseTo(11.7);
    expect(placement.delaySeconds).toBeCloseTo(1.7);
    expect(placement.bufferOffsetSeconds).toBe(0);
  });

  it("trims the buffer when a take begins before the mix range", () => {
    const placement = calculateTimelinePlacement({
      timelineStartSeconds: 8,
      rangeStartSeconds: 10,
      rangeDurationSeconds: 5,
      bufferDurationSeconds: 6,
    });
    expect(placement.delaySeconds).toBe(0);
    expect(placement.bufferOffsetSeconds).toBe(2);
    expect(placement.availableSeconds).toBe(4);
  });

  it("uses a stable drag direction and clamps extreme offsets", () => {
    expect(offsetFromDrag({ originalOffsetMs: 0, deltaPixels: 10,
      laneWidthPixels: 100, timelineDurationSeconds: 10 })).toBe(-1000);
    expect(offsetFromDrag({ originalOffsetMs: 0, deltaPixels: -1000,
      laneWidthPixels: 100, timelineDurationSeconds: 10 })).toBe(2000);
  });

  it("restarts a loop at either boundary", () => {
    expect(normalizeLoopTime(4.9, 5, 8)).toBe(5);
    expect(normalizeLoopTime(8, 5, 8)).toBe(5);
    expect(normalizeLoopTime(6, 5, 8)).toBe(6);
  });
});

describe("recorder state machine", () => {
  it("allows the successful recording path", () => {
    expect(canTransitionRecorder("idle", "requesting")).toBe(true);
    expect(canTransitionRecorder("requesting", "recording")).toBe(true);
    expect(canTransitionRecorder("recording", "preview")).toBe(true);
    expect(canTransitionRecorder("preview", "uploading")).toBe(true);
    expect(canTransitionRecorder("uploading", "uploaded")).toBe(true);
  });

  it("rejects impossible jumps", () => {
    expect(canTransitionRecorder("idle", "uploaded")).toBe(false);
    expect(canTransitionRecorder("recording", "uploading")).toBe(false);
  });
});
