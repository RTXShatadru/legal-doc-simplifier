import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ChatPanel from "./ChatPanel";
import { api } from "../api";

vi.mock("../api", () => ({
  api: { getChatHistory: vi.fn(), sendChatMessage: vi.fn() },
}));

const source = { clause_index: 2, page: 4, text: "Payment is due within thirty days." };
const defaultProps = {
  docId: "document-a",
  filename: "Agreement.pdf",
  documentType: "Agreement",
  domain: "property",
  workflow: "review",
  onSource: vi.fn(),
};

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

beforeEach(() => {
  api.getChatHistory.mockReset().mockResolvedValue([]);
  api.sendChatMessage.mockReset().mockResolvedValue({ answer: "Payment is due within 30 days. [3]", sources: [source] });
});

it("prefills a law question without sending and preserves the selected period", async () => {
  render(<ChatPanel {...defaultProps} legalQuestion={{text:"Explain IPC section 420.",period:"before",nonce:1}}/>);
  const input=screen.getByRole("textbox",{name:"Question about this document"});
  await waitFor(() => expect(input).toBeEnabled());
  expect(input).toHaveValue("Explain IPC section 420.");
  expect(screen.getByRole("checkbox",{name:"Include central Indian law references"})).toBeChecked();
  expect(api.sendChatMessage).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button",{name:"Send"}));
  await waitFor(() => expect(api.sendChatMessage).toHaveBeenCalledWith("document-a","Explain IPC section 420.",{include_law:true,legal_period:"before"}));
});

it("restores mixed legal and document sources without turning laws into document sections", async () => {
  const law={kind:"law",id:"IPC420",label:"IPC 420 · Cheating",status:"historical",summary:"A reference summary.",url:"https://session.delhi.gov.in/session/indian-penal-code",period:"unknown",checked_on:"2026-10-31",version:"1"};
  api.getChatHistory.mockResolvedValue([{role:"assistant",content:"The allegation is in [3]. Check [LAW:IPC420].",sources:[source,law]}]);
  render(<ChatPanel {...defaultProps}/>);
  const link=await screen.findByRole("link",{name:"Official source: IPC 420 · Cheating"});
  expect(link).toHaveAttribute("href",law.url);
  expect(screen.getByRole("button",{name:"Open section 3, page 4"})).toBeInTheDocument();
  expect(screen.queryByText(/Section NaN/)).not.toBeInTheDocument();
  expect(screen.getByRole("checkbox",{name:"Include central Indian law references"})).toBeChecked();
});

describe("document chatbot", () => {
  it("restores saved questions, answers and source links for this document", async () => {
    const onSource = vi.fn();
    api.getChatHistory.mockResolvedValue([
      { role: "user", content: "When is payment due?" },
      { role: "assistant", content: "Within thirty days. [3]", sources: [source] },
    ]);
    render(<ChatPanel {...defaultProps} onSource={onSource} />);

    expect(await screen.findByText("When is payment due?")).toBeInTheDocument();
    expect(screen.getByText(/Within thirty days/)).toBeInTheDocument();
    expect(api.getChatHistory).toHaveBeenCalledWith("document-a");
    await userEvent.click(screen.getByRole("button", { name: "Open section 3, page 4" }));
    expect(onSource).toHaveBeenCalledWith(2);
    expect(api.sendChatMessage).not.toHaveBeenCalled();
  });

  it("sends a typed question and renders the grounded response with clickable evidence", async () => {
    const onSource = vi.fn();
    render(<ChatPanel {...defaultProps} onSource={onSource} />);
    const input = screen.getByRole("textbox", { name: "Question about this document" });
    await waitFor(() => expect(input).toBeEnabled());
    await userEvent.type(input, "  When must I pay?  ");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText(/Payment is due within 30 days/)).toBeInTheDocument();
    expect(api.sendChatMessage).toHaveBeenCalledExactlyOnceWith("document-a", "When must I pay?");
    expect(input).toHaveValue("");
    await userEvent.click(screen.getByText(/1 source passage/));
    expect(screen.getByText(source.text)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Section 3 · Page 4" }));
    expect(onSource).toHaveBeenCalledWith(2);
  });

  it("preserves a failed question for retry without adding a phantom answer or duplicate question", async () => {
    api.sendChatMessage.mockRejectedValueOnce(new Error("The AI service is temporarily unavailable."));
    render(<ChatPanel {...defaultProps} />);
    const input = screen.getByRole("textbox", { name: "Question about this document" });
    await waitFor(() => expect(input).toBeEnabled());
    await userEvent.type(input, "Explain the payment clause.");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("temporarily unavailable");
    expect(input).toHaveValue("Explain the payment clause.");
    const log = screen.getByRole("log", { name: "Document conversation" });
    expect(within(log).queryByText("Explain the payment clause.")).not.toBeInTheDocument();
    expect(within(log).queryByText("SimplyDoc")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText(/Payment is due within 30 days/);
    expect(within(log).getAllByText("Explain the payment clause.")).toHaveLength(1);
    expect(api.sendChatMessage).toHaveBeenCalledTimes(2);
  });

  it("keeps a pending answer when inactive and does not move focus from the source panel", async () => {
    const reply = deferred();
    api.sendChatMessage.mockReturnValue(reply.promise);
    const props = { ...defaultProps, active: true };
    const { rerender } = render(<><button>Source text</button><ChatPanel {...props} /></>);
    const input = screen.getByRole("textbox", { name: "Question about this document" });
    await waitFor(() => expect(input).toBeEnabled());
    await userEvent.type(input, "What is the payment deadline?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    rerender(<><button>Source text</button><ChatPanel {...props} active={false} /></>);
    const sourceTab = screen.getByRole("button", { name: "Source text" });
    sourceTab.focus();

    await act(async () => reply.resolve({ answer: "The deadline is thirty days. [3]", sources: [source] }));
    expect(sourceTab).toHaveFocus();
    rerender(<><button>Source text</button><ChatPanel {...props} active /></>);
    expect(await screen.findByText(/The deadline is thirty days/)).toBeInTheDocument();
    expect(api.getChatHistory).toHaveBeenCalledTimes(1);
    expect(api.sendChatMessage).toHaveBeenCalledTimes(1);
  });

  it("requires history to load before sending, and can recover from a history fetch failure", async () => {
    api.getChatHistory.mockRejectedValueOnce(new Error("Cannot load the saved conversation."));
    render(<ChatPanel {...defaultProps} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot load");
    const input = screen.getByRole("textbox", { name: "Question about this document" });
    expect(input).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Reload conversation" }));
    await waitFor(() => expect(input).toBeEnabled());
    expect(api.getChatHistory).toHaveBeenCalledTimes(2);
  });

  it("does not let a response for a previous document leak into the next document", async () => {
    const reply = deferred();
    api.sendChatMessage.mockReturnValue(reply.promise);
    const { rerender } = render(<ChatPanel key="document-a" {...defaultProps} />);
    const input = screen.getByRole("textbox", { name: "Question about this document" });
    await waitFor(() => expect(input).toBeEnabled());
    await userEvent.type(input, "Question for document A");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    rerender(<ChatPanel key="document-b" {...defaultProps} docId="document-b" filename="Second.pdf" />);
    await waitFor(() => expect(api.getChatHistory).toHaveBeenLastCalledWith("document-b"));
    await act(async () => reply.resolve({ answer: "Answer for document A", sources: [] }));
    expect(screen.queryByText("Answer for document A")).not.toBeInTheDocument();
    expect(screen.queryByText("Question for document A")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Question about this document" })).toBeEnabled());
  });

  it.each([
    ["hr", "resume", "Which skills are listed in my resume?"],
    ["hr", "review", "What salary and benefits are stated?"],
    ["medical", "review", "Which values are outside the printed reference ranges?"],
  ])("offers and sends a useful starter for %s / %s", async (domain, workflow, starter) => {
    render(<ChatPanel {...defaultProps} domain={domain} workflow={workflow} />);
    await userEvent.click(await screen.findByRole("button", { name: starter }));
    await screen.findByText(/Payment is due within 30 days/);
    expect(api.sendChatMessage).toHaveBeenCalledExactlyOnceWith("document-a", starter);
  });
});
