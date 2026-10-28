import { act, screen } from "@testing-library/react";
import { events, investigation } from "../test/fixtures";
import { mockFetch, renderAt } from "../test/render";
import { InvestigationPage } from "./InvestigationPage";

type Listener = (e: MessageEvent<string>) => void;

class FakeEventSource {
  static last: FakeEventSource | null = null;
  listeners: Record<string, Listener[]> = {};
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(readonly url: string) {
    FakeEventSource.last = this;
  }
  addEventListener(type: string, fn: Listener) {
    (this.listeners[type] ??= []).push(fn);
  }
  emit(type: string, data: unknown) {
    for (const fn of this.listeners[type] ?? []) fn(new MessageEvent(type, { data: JSON.stringify(data) }));
  }
  close() {
    this.closed = true;
  }
}

const at = { path: "/investigations/:id", route: "/investigations/inv-1" };

describe("InvestigationPage", () => {
  beforeEach(() => vi.stubGlobal("EventSource", FakeEventSource));
  afterEach(() => vi.unstubAllGlobals());

  it("renders real state, per-vendor errors and streamed events", async () => {
    mockFetch({ "/api/investigations/inv-1": investigation() });
    renderAt(<InvestigationPage />, at);
    expect(await screen.findByText("Alpha vs Beta")).toBeInTheDocument();
    expect(screen.getByText("No policy pages could be retrieved for this vendor")).toBeInTheDocument();
    expect(screen.getByText("Parse terms").closest("[aria-current]")).toHaveAttribute("aria-current", "step");
    expect(FakeEventSource.last?.url).toContain("/api/investigations/inv-1/events");
    act(() => {
      FakeEventSource.last?.onopen?.();
      for (const e of events) FakeEventSource.last?.emit("progress", e);
    });
    expect(screen.getByText("Research failed: blocked")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("offers the report when finished and closes the stream", async () => {
    mockFetch({ "/api/investigations/inv-1": investigation({ status: "partial", is_terminal: true, report_id: "rep-1", error: { message: "1 of 2 vendors could not be investigated", category: "partial" } }) });
    renderAt(<InvestigationPage />, at);
    expect(await screen.findByRole("link", { name: /view comparison/i })).toHaveAttribute("href", "/reports/rep-1");
    act(() => FakeEventSource.last?.emit("status", { status: "partial", is_terminal: true, report_id: "rep-1" }));
    expect(FakeEventSource.last?.closed).toBe(true);
  });

  it("shows a failure without pretending success", async () => {
    mockFetch({ "/api/investigations/inv-1": investigation({ status: "failed", is_terminal: true, error: { message: "Every vendor investigation failed; no report was produced.", category: "unavailable" } }) });
    renderAt(<InvestigationPage />, at);
    expect(await screen.findByText("Investigation failed")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /view comparison/i })).not.toBeInTheDocument();
  });
});
