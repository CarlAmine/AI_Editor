import React from "react";
import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";

import { ChatPanel, resolveChatSubmitTarget } from "./ChatPanel";

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

describe("ChatPanel final plan rendering", () => {
  it("includes the final plan card when awaiting_final_confirmation", () => {
    const html = renderToString(
      <ChatPanel
        apiBase="http://localhost"
        analyzerOutput=""
        currentState={{
          phase: "awaiting_final_confirmation",
          ready_to_submit: true,
          primary_url: "https://youtube.com/watch?v=ref",
          reference_slots: [
            { slot_id: 1, start: 0, end: 2, duration: 2, role: "hook" },
          ],
          sources: [
            { label: 1, url: "https://youtube.com/watch?v=source" },
          ],
          slot_mapping: [
            { slot_id: 1, clip_url: "https://youtube.com/watch?v=source" },
          ],
          music_mode: "original",
          aspect_ratio: "9:16",
          refit_mode: "crop_center",
        }}
      />
    );

    expect(html).toContain("Confirm and render");
    expect(html).toContain("Edit plan");
    expect(html).toContain("Ready to render");
  });
});
