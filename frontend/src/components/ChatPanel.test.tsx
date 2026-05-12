import { describe, expect, it } from "vitest";

import { resolveChatSubmitTarget } from "./ChatPanel";

describe("resolveChatSubmitTarget", () => {
  it("routes paused jobs to the resume endpoint", () => {
    expect(
      resolveChatSubmitTarget(
        "http://localhost:10000",
        "waiting_for_user_input",
        "job-123"
      )
    ).toEqual({
      endpoint: "http://localhost:10000/jobs/job-123/resume",
      isResume: true,
    });
  });

  it("routes blocked jobs with a job id to the resume endpoint", () => {
    expect(
      resolveChatSubmitTarget(
        "http://localhost:10000",
        "blocked",
        "job-123"
      )
    ).toEqual({
      endpoint: "http://localhost:10000/jobs/job-123/resume",
      isResume: true,
    });
  });

  it("keeps standalone brief chat on the chat endpoint", () => {
    expect(
      resolveChatSubmitTarget("http://localhost:10000", "working", "job-123")
    ).toEqual({
      endpoint: "http://localhost:10000/chat",
      isResume: false,
    });
  });
});
