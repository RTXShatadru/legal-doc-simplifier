import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DocumentView from "./DocumentView";
import { api } from "../api";

vi.mock("../api", () => ({
  api: { getDocument: vi.fn(), getChatHistory: vi.fn(), sendChatMessage: vi.fn(), getLegalReferences: vi.fn() },
}));

const analysis = {
  mode: "groq", document_type: "Employment agreement", plain_summary: "An employment agreement with a notice period.",
  key_terms: [], risky_clauses: [], disclaimer: "Verify the original wording.",
};
const document = {
  id: "document-a", domain: "hr", workflow: "review", filename: "Agreement.pdf", status: "ready",
  uploaded_at: 1750000000, page_count: 1, source_revision: "revision-1", analysis,
  clauses: [{ clause_index: 0, page: 1, text: "The notice period is thirty days." }],
};
const props = { docId: "document-a", onReady: vi.fn(), onDelete: vi.fn(), onBack: vi.fn() };

beforeEach(() => {
  api.getDocument.mockReset().mockResolvedValue(document);
  api.getChatHistory.mockReset().mockResolvedValue([]);
  api.sendChatMessage.mockReset();
  api.getLegalReferences.mockReset();
});

it("shows excluded resume suggestions and opens the affected source section", async () => {
  api.getDocument.mockResolvedValue({...document,workflow:"resume",analysis:{...analysis,
    verification_warnings:[{omitted_facts:1,clause_indices:[0]}],
    resume_profile:{skills_clean:[],skills_detail:[]},
  }});
  render(<DocumentView {...props}/>);
  const notice=await screen.findByRole("region",{name:"Resume source checks"});
  expect(within(notice).getByText("1 suggested entry could not be verified against the source and was excluded.")).toBeVisible();
  await userEvent.click(within(notice).getByRole("button",{name:"Check section 1 · Page 1"}));
  expect(await screen.findByRole("heading",{name:"The original wording"})).toBeVisible();
  expect(within(screen.getByRole("article")).getByText(document.clauses[0].text)).toBeVisible();
  expect(notice).toBeVisible();
});

it("opens a legal-reference question in the existing document chat without auto-sending", async () => {
  api.getLegalReferences.mockResolvedValue({entries:[{id:"TPA54",act:"TPA",section:"54",title:"Sale",act_name:"Transfer of Property Act, 1882",summary:"Sale summary.",reason:"Topic match",evidence:[],related:[],source_url:"https://session.delhi.gov.in/session/transfer-property-act",source_note:"Central provision",checked_on:"2026-10-31"}],count:35,notice:"Central only",transition:"Check the conduct date",commencement_url:"https://www.indiacode.nic.in/",mapping_url:"https://www.ncrb.mha.gov.in/",version:"1"});
  render(<DocumentView {...props}/>);
  await userEvent.click(await screen.findByRole("button",{name:"Legal references",exact:true}));
  await userEvent.click(await screen.findByRole("button",{name:"Ask about this"}));
  const input=screen.getByRole("textbox",{name:"Question about this document"});
  await waitFor(() => expect(input).toBeEnabled());
  expect(input).toHaveValue("Explain TPA section 54 and what I should verify in this document.");
  expect(screen.getByRole("checkbox",{name:"Include central Indian law references"})).toBeChecked();
  expect(api.sendChatMessage).not.toHaveBeenCalled();
});

describe("chat from document review", () => {
  it.each(["queued", "processing", "failed"])("does not offer document chat before an analysis is ready (%s)", async status => {
    api.getDocument.mockResolvedValue({ ...document, status, analysis: null });
    render(<DocumentView {...props} />);
    await screen.findByRole("heading", { name: "Agreement.pdf" });
    expect(screen.queryByRole("button", { name: "Chat with document" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Document chat" })).not.toBeInTheDocument();
    expect(api.getChatHistory).not.toHaveBeenCalled();
  });

  it("opens chat for an HR document and preserves the draft while checking cited source text", async () => {
    api.getChatHistory.mockResolvedValue([
      { role: "user", content: "How long is the notice period?" },
      { role: "assistant", content: "The notice period is thirty days. [1]", sources: document.clauses },
    ]);
    render(<DocumentView {...props} />);
    await userEvent.click(await screen.findByRole("button", { name: "Chat with document" }));
    const input = screen.getByRole("textbox", { name: "Question about this document" });
    await waitFor(() => expect(input).toBeEnabled());
    expect(screen.getByRole("heading", { name: "Document chat" })).toBeVisible();
    await userEvent.type(input, "Does that include weekends?");
    await userEvent.click(screen.getByRole("button", { name: "Open section 1, page 1" }));

    expect(await screen.findByRole("heading", { name: "The original wording" })).toBeVisible();
    expect(input).not.toBeVisible();
    expect(within(screen.getByRole("article")).getByText("The notice period is thirty days.")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Back to document chat" }));
    expect(screen.getByRole("textbox", { name: "Question about this document" })).toBe(input);
    expect(input).toHaveValue("Does that include weekends?");
    expect(api.getChatHistory).toHaveBeenCalledTimes(1);
  });

  it("retains a request and its answer while the user switches away from chat", async () => {
    let finish;
    api.sendChatMessage.mockReturnValue(new Promise(resolve => { finish = resolve; }));
    render(<DocumentView {...props} />);
    await userEvent.click(await screen.findByRole("button", { name: "Chat with document" }));
    const input = screen.getByRole("textbox", { name: "Question about this document" });
    await waitFor(() => expect(input).toBeEnabled());
    await userEvent.type(input, "Explain the notice period.");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await userEvent.click(screen.getByRole("button", { name: "Overview" }));
    expect(input).not.toBeVisible();
    await act(async () => finish({ answer: "Give notice thirty days before leaving. [1]", sources: document.clauses }));
    expect(screen.getByRole("button", { name: "Overview" })).toHaveFocus();

    await userEvent.click(screen.getByRole("button", { name: "Document chat" }));
    expect(screen.getByRole("textbox", { name: "Question about this document" })).toBe(input);
    expect(await screen.findByText(/Give notice thirty days before leaving/)).toBeVisible();
    expect(api.sendChatMessage).toHaveBeenCalledExactlyOnceWith("document-a", "Explain the notice period.");
    expect(api.getChatHistory).toHaveBeenCalledTimes(1);
  });
});
