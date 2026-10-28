import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { evidence, meta, report } from "../test/fixtures";
import { mockFetch, renderAt } from "../test/render";
import { ReportPage } from "./ReportPage";

const at = { path: "/reports/:id", route: "/reports/rep-1" };

describe("ReportPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders the matrix, recommendation, statuses and risk flags", async () => {
    mockFetch({ "/api/meta": meta, "/api/reports/rep-1/evidence": { report_id: "rep-1", items: evidence }, "/api/reports/rep-1": report });
    renderAt(<ReportPage />, at);
    expect(await screen.findByRole("heading", { name: /alpha best matches/i })).toBeInTheDocument();
    expect(screen.getByText(/confidence: medium/i)).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getByRole("columnheader", { name: /alpha \(recommended\)/i })).toBeInTheDocument();
    expect(within(table).getByText("30 days")).toBeInTheDocument();
    expect(within(table).getByText("No fee (stated)")).toBeInTheDocument();
    expect(within(table).getAllByText("Not stated").length).toBeGreaterThan(0);
    expect(within(table).getByText("Conflicting")).toBeInTheDocument();
    expect(screen.getByText("Beta: Refund window: Conflicting: 14 days vs 30 days.")).toBeInTheDocument();
    expect(screen.getByText(/AI summary was discarded/i)).toBeInTheDocument();
  });

  it("opens evidence with source links and verification states", async () => {
    mockFetch({ "/api/meta": meta, "/api/reports/rep-1/evidence": { report_id: "rep-1", items: evidence }, "/api/reports/rep-1": report });
    renderAt(<ReportPage />, at);
    const user = userEvent.setup();
    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /show evidence for beta refund window/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Refunds within 14 days of purchase/)).toBeInTheDocument();
    expect(within(dialog).getByText("Quote verified")).toBeInTheDocument();
    expect(within(dialog).getByText("Quote not found in page")).toBeInTheDocument();
    const link = within(dialog).getByRole("link", { name: /refunds/i });
    expect(link).toHaveAttribute("href", "https://beta.example/refunds");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows an error state for a missing report", async () => {
    mockFetch({ "/api/meta": meta });
    renderAt(<ReportPage />, at);
    expect(await screen.findByText("Report unavailable")).toBeInTheDocument();
  });
});
