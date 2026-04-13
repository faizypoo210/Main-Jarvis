import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Memory } from "./Memory";

vi.mock("../lib/api", () => ({
  getMemoryCounts: vi.fn(() =>
    Promise.resolve({ by_type: {}, active: 0, archived: 0 })
  ),
  getMemoryList: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
}));

describe("Memory", () => {
  it("surfaces create / promote entry points after load", async () => {
    render(
      <MemoryRouter>
        <Memory />
      </MemoryRouter>
    );
    expect(await screen.findByRole("heading", { name: /^memory$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^new memory$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^promote from mission$/i })).toBeInTheDocument();
  });
});
