import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { ResumeProfile } from "./DomainDetails";

const original={name:[],email:[],phone:[],skills_clean:[],skills_detail:[],experience:[],education:[]};

it("shows projects and certifications with their own source links", async () => {
  const onSource=vi.fn();
  render(<ResumeProfile onSource={onSource} profile={{...original,
    project:[{value:"Document Reader",detail:"A stated project.",quote:"Project: Document Reader",clause_index:2,page:1}],
    certification:[{value:"Cloud Foundations",detail:"A stated certificate.",quote:"Certificate: Cloud Foundations",clause_index:5,page:2}]}}/>);
  expect(screen.getByRole("heading",{name:"Projects"})).toBeInTheDocument();
  expect(screen.getByRole("heading",{name:"Certifications"})).toBeInTheDocument();
  expect(screen.getByText("Cloud Foundations")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button",{name:"Section 6 · Page 2"}));
  expect(onSource).toHaveBeenCalledWith(5);
});

it("still renders a saved resume from before the additional categories", () => {
  render(<ResumeProfile profile={original} onSource={vi.fn()}/>);
  expect(screen.getByRole("heading",{name:"Resume profile"})).toBeInTheDocument();
  expect(screen.getByRole("heading",{name:"Certifications"})).toBeInTheDocument();
});
