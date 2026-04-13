import { describe, expect, it } from "vitest";
import { parseSseDataPayloads } from "./api";

describe("parseSseDataPayloads", () => {
  it("ignores comment-only blocks and extracts data payloads", () => {
    const buf = "retry: 5000\n\n: keepalive\n\ndata: {\"type\":\"mission\"}\n\n";
    const { payloads, rest } = parseSseDataPayloads(buf);
    expect(payloads).toEqual(['{"type":"mission"}']);
    expect(rest).toBe("");
  });

  it("keeps incomplete trailing data in rest until a full block arrives", () => {
    const { payloads, rest } = parseSseDataPayloads('data: {"x":');
    expect(payloads).toEqual([]);
    expect(rest).toBe('data: {"x":');
  });
});
