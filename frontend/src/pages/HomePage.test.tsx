import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { meta } from "../test/fixtures";
import { mockFetch, renderAt } from "../test/render";
import { HomePage } from "./HomePage";

const empty = { items: [], total: 0, limit: 6, offset: 0 };

describe("HomePage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("requires two vendors before investigating", async () => {
    mockFetch({ "/api/meta": meta, "/api/investigations?limit": empty });
    renderAt(<HomePage />);
    const user = userEvent.setup();
    const start = await screen.findByRole("button", { name: /^investigate/i });
    expect(start).toBeDisabled();
    await user.type(screen.getByLabelText(/vendor name/i), "Coursera");
    await user.click(screen.getByRole("button", { name: /^add$/i }));
    expect(start).toBeDisabled();
    expect(screen.getByText("Add 1 more vendor")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/vendor name/i), "Udemy");
    await user.click(screen.getByRole("button", { name: /^add$/i }));
    expect(start).toBeEnabled();
  });

  it("shows validation errors and supports removing vendors", async () => {
    mockFetch({ "/api/meta": meta, "/api/investigations?limit": empty });
    renderAt(<HomePage />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /^add$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a vendor name.");
    await user.type(screen.getByLabelText(/vendor name/i), "Coursera");
    await user.type(screen.getByLabelText(/official site/i), "127.0.0.1");
    await user.click(screen.getByRole("button", { name: /^add$/i }));
    expect(screen.getByRole("alert")).toHaveTextContent(/not an IP address/);
    await user.clear(screen.getByLabelText(/official site/i));
    await user.click(screen.getByRole("button", { name: /^add$/i }));
    const list = screen.getByRole("list", { name: /selected vendors/i });
    expect(list).toHaveTextContent("Coursera");
    await user.click(screen.getByRole("button", { name: "Remove Coursera" }));
    expect(list).not.toHaveTextContent("Coursera");
  });

  it("submits vendors and ordered priorities, then navigates", async () => {
    const fetchMock = mockFetch({
      "/api/meta": meta,
      "/api/investigations?limit": empty,
      "/api/investigations": { id: "inv-9", status: "queued" },
    });
    renderAt(<HomePage />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /load demo vendors/i }));
    await user.click(screen.getByRole("button", { name: "Easiest cancellation" }));
    await user.click(screen.getByRole("button", { name: "Longest refund window" }));
    await user.click(screen.getByRole("button", { name: /^investigate/i }));
    await waitFor(() => expect(screen.getByText("navigated")).toBeInTheDocument());
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    const body = JSON.parse(String(post?.[1]?.body));
    expect(body.vendors).toHaveLength(3);
    expect(body.priorities).toEqual([
      { criterion: "easiest_cancellation", weight: 3 },
      { criterion: "longest_refund_window", weight: 2 },
    ]);
    expect((post?.[1]?.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
  });

  it("surfaces API errors when starting fails", async () => {
    mockFetch({
      "/api/meta": meta,
      "/api/investigations?limit": empty,
      "/api/investigations": () =>
        new Response(JSON.stringify({ error: { code: "invalid_request", message: "Domain 'localhost' is not a public website" } }), { status: 422 }),
    });
    renderAt(<HomePage />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /load demo vendors/i }));
    await user.click(screen.getByRole("button", { name: /^investigate/i }));
    expect(await screen.findByText("Domain 'localhost' is not a public website")).toBeInTheDocument();
  });

  it("shows an error state when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("network"); }));
    renderAt(<HomePage />);
    expect(await screen.findByText(/cannot reach the clauselens api/i, {}, { timeout: 4000 })).toBeInTheDocument();
  });
});
