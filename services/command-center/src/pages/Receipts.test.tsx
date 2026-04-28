import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Receipts } from "./Receipts";

vi.mock("../lib/api", () => ({
  getReceipts: vi.fn(),
}));

import * as api from "../lib/api";

describe("Receipts", () => {
  it("shows empty copy when the API returns no receipts", async () => {
    vi.mocked(api.getReceipts).mockResolvedValueOnce([]);
    render(
      <MemoryRouter>
        <Receipts />
      </MemoryRouter>
    );
    expect(
      await screen.findByText(/No receipts yet\. Receipts appear here after missions run\./i)
    ).toBeInTheDocument();
  });

  it("renders receipt_type for each row when data is returned", async () => {
    vi.mocked(api.getReceipts).mockResolvedValueOnce([
      {
        id: "11111111-1111-1111-1111-111111111111",
        mission_id: null,
        receipt_type: "openclaw_execution",
        source: "executor",
        payload: {},
        summary: "First",
        created_at: "2026-01-01T12:00:00.000Z",
      },
      {
        id: "22222222-2222-2222-2222-222222222222",
        mission_id: null,
        receipt_type: "integration_github",
        source: "workflow",
        payload: {},
        summary: "Second",
        created_at: "2026-01-02T12:00:00.000Z",
      },
    ]);
    render(
      <MemoryRouter>
        <Receipts />
      </MemoryRouter>
    );
    expect(await screen.findByText("openclaw_execution")).toBeInTheDocument();
    expect(screen.getByText("integration_github")).toBeInTheDocument();
  });
});
