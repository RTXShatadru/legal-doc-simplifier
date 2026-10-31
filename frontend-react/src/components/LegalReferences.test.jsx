import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import LegalReferences from "./LegalReferences";
import { api } from "../api";

vi.mock("../api", () => ({ api: { getLegalReferences: vi.fn() } }));
const entry = { id:"IPC420", act:"IPC", section:"420", title:"Cheating and delivery of property", act_name:"Indian Penal Code, 1860",
  status:"historical", summary:"Verify deception and dishonest inducement.", reason:"Requested provision", evidence:[{clause_index:2,page:4,reason:"Named provision"}],
  related:[{id:"BNS318(4)",label:"BNS 318(4)"}], source_url:"https://session.delhi.gov.in/session/indian-penal-code", source_note:"Historical reference copy", checked_on:"2026-10-31" };
const data = { entries:[entry], count:35, checked_on:"2026-10-31", version:"2026-10-31.1", notice:"Central provisions only.", transition:"Check the conduct date.",
  commencement_url:"https://www.mha.gov.in/notification.pdf", mapping_url:"https://www.ncrb.mha.gov.in/table.html" };
beforeEach(() => api.getLegalReferences.mockReset().mockResolvedValue(data));

it("shows historical context, official sources and document evidence", async () => {
  const onSource=vi.fn(),onAsk=vi.fn();
  render(<LegalReferences docId="one" onSource={onSource} onAsk={onAsk}/>);
  expect(await screen.findByText("HISTORICAL IPC")).toBeInTheDocument();
  expect(screen.getByRole("link",{name:"Official source"})).toHaveAttribute("href",entry.source_url);
  await userEvent.click(screen.getByRole("button",{name:"Document section 3 · Page 4"}));
  expect(onSource).toHaveBeenCalledWith(2);
  await userEvent.selectOptions(screen.getByLabelText("Date of alleged conduct"),"after");
  await screen.findByText(entry.title);
  await userEvent.click(screen.getByRole("button",{name:"Ask about this"}));
  expect(onAsk).toHaveBeenCalledWith({text:"Explain IPC section 420 and what I should verify in this document.",period:"after"});
});

it("searches explicitly and follows the BNS cross-reference", async () => {
  render(<LegalReferences docId="one" onSource={vi.fn()} onAsk={vi.fn()}/>);
  await screen.findByText(entry.title);
  await userEvent.type(screen.getByRole("textbox",{name:"Search laws or sections"}),"IPC 420");
  await userEvent.click(screen.getByRole("button",{name:"Search",exact:true}));
  await waitFor(() => expect(api.getLegalReferences).toHaveBeenLastCalledWith("one",{q:"IPC 420",period:"unknown",act:"all",browse:false}));
  await screen.findByText(entry.title);
  await userEvent.click(screen.getByRole("button",{name:"BNS 318(4)"}));
  await waitFor(() => expect(api.getLegalReferences).toHaveBeenLastCalledWith("one",{q:"BNS 318(4)",period:"unknown",act:"all",browse:false}));
});

it("explains coverage gaps and lets users browse", async () => {
  api.getLegalReferences.mockResolvedValue({...data,entries:[]});
  render(<LegalReferences docId="one" onSource={vi.fn()} onAsk={vi.fn()}/>);
  expect(await screen.findByText("No matching reference in this collection")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button",{name:"Browse collection"}));
  await waitFor(() => expect(api.getLegalReferences).toHaveBeenLastCalledWith("one",{q:"",period:"unknown",act:"all",browse:true}));
});

it("does not show a stale response after filters change", async () => {
  let finish;
  api.getLegalReferences.mockImplementationOnce(() => new Promise(resolve => { finish=resolve; })).mockResolvedValue({...data,entries:[]});
  render(<LegalReferences docId="one" onSource={vi.fn()} onAsk={vi.fn()}/>);
  await userEvent.selectOptions(screen.getByLabelText("Act"),"REG");
  await screen.findByText("No matching reference in this collection");
  finish(data);
  await waitFor(() => expect(screen.queryByText(entry.title)).not.toBeInTheDocument());
});
