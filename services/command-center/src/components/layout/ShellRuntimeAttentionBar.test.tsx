import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ShellRuntimeSummary } from "../../lib/operatorRuntimeHealth";
import { ShellRuntimeAttentionBar } from "./ShellRuntimeStatus";

const mockUseShellHealth = vi.fn();

vi.mock("../../contexts/ShellHealthContext", () => ({
  useShellHealth: () => mockUseShellHealth(),
}));

function summary(partial: Partial<ShellRuntimeSummary>): ShellRuntimeSummary {
  return {
    overall: "attention",
    systemHealthFetchFailed: false,
    pills: {
      cp: { state: "healthy", short: "OK" },
      sse: { state: "degraded", short: "REC" },
      wr: { state: "healthy", short: "OK" },
      hb: { state: "healthy", short: "OK", openCount: null },
    },
    bannerLines: [],
    ...partial,
  };
}

describe("ShellRuntimeAttentionBar", () => {
  it("renders nothing when overall is ok", () => {
    mockUseShellHealth.mockReturnValue({
      summary: summary({ overall: "ok", bannerLines: [] }),
    });
    const { container } = render(
      <MemoryRouter>
        <ShellRuntimeAttentionBar />
      </MemoryRouter>
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders status banner lines for operator attention", () => {
    mockUseShellHealth.mockReturnValue({
      summary: summary({
        overall: "attention",
        bannerLines: ["Live stream reconnecting — mission list may be stale briefly."],
      }),
    });
    render(
      <MemoryRouter>
        <ShellRuntimeAttentionBar />
      </MemoryRouter>
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText(/reconnecting/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /system health/i })).toHaveAttribute("href", "/system");
  });
});
