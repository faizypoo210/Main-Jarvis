import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { hasError: boolean };

/**
 * Prevents a single route/component failure from blanking the entire Command Center shell.
 */
export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[Command Center] route render error:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-3 bg-[var(--bg-void)] px-6 text-center">
          <p className="max-w-md text-sm text-[var(--text-secondary)]">
            Command Center failed to render this view.
          </p>
          <p className="max-w-md text-xs text-[var(--text-muted)]">
            Reload the page or inspect the latest frontend error in the browser console.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-surface)] px-4 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)]/80"
          >
            Reload page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
