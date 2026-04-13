import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QuickCommandPalette } from "./QuickCommandPalette";

describe("QuickCommandPalette", () => {
  it("exposes quick mission intake when open", () => {
    const onClose = vi.fn();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <QuickCommandPalette open onClose={onClose} onSubmit={onSubmit} />
    );
    expect(screen.getByRole("dialog", { name: /quick command/i })).toBeInTheDocument();
    expect(
      screen.getByText(/sends a short command to the control plane/i)
    ).toBeInTheDocument();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <QuickCommandPalette open={false} onClose={() => undefined} onSubmit={async () => undefined} />
    );
    expect(container.firstChild).toBeNull();
  });
});
