import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../lib/api";
import { ConversationThread } from "./ConversationThread";

vi.mock("../../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/api")>();
  return {
    ...actual,
    createCommand: vi.fn(),
  };
});

vi.mock("../layout/AppShell", () => ({
  useShellOutlet: () => ({
    threadMissionId: null,
    setThreadMissionId: vi.fn(),
    openVoiceMode: vi.fn(),
  }),
}));

vi.mock("../../hooks/useControlPlane", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../hooks/useControlPlane")>();
  return {
    ...actual,
    useControlPlaneLive: () => ({
      missions: [],
      missionsLoading: false,
      missionsError: null,
      pendingApprovals: [],
      pendingLoading: false,
      pendingError: null,
      eventsByMissionId: {},
      missionById: {},
      streamConnected: false,
      streamError: "test",
      streamPhase: "reconnecting" as const,
      eventStreamRevision: 0,
      refetchMissions: async () => undefined,
      refetchPendingApprovals: async () => undefined,
      bootstrapMission: async () => undefined,
      hydrateMissionBundle: () => undefined,
    }),
    useResolveApprovalAction: () => ({
      resolve: vi.fn(),
      resolvingApprovalId: null,
      resolveErrorApprovalId: null,
      clearResolveError: vi.fn(),
      lastResolved: null,
      clearResolvedState: vi.fn(),
      recentlyResolvedDecisionFor: () => null,
    }),
  };
});

const createCommandMock = vi.mocked(api.createCommand);

function getComposerInput(): HTMLInputElement {
  const inputs = screen.getAllByRole("textbox", { name: /composer command/i });
  return inputs[0] as HTMLInputElement;
}

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  createCommandMock.mockReset();
});

describe("ConversationThread composer (SSE-independent)", () => {
  it("keeps the message input enabled while streamPhase is reconnecting", () => {
    render(<ConversationThread onVoiceClick={() => undefined} />);
    const input = getComposerInput();
    expect(input).not.toBeDisabled();
  });

  it("clears submitting after createCommand fails so the operator can retry", async () => {
    createCommandMock.mockRejectedValueOnce(new Error("network"));

    render(<ConversationThread onVoiceClick={() => undefined} />);
    const input = getComposerInput();
    fireEvent.change(input, { target: { value: "hello" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText(/could not reach jarvis/i)).toBeInTheDocument();
    });
    expect(input).not.toBeDisabled();
  });
});
