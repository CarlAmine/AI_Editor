import React from "react";
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import {
  getControllerStatusLabel,
  VideoPipelineResultNotice,
  type PipelineResult,
} from "./VideoPipelinePanel";

const baseResult: PipelineResult = {
  success: false,
  error: "Pipeline paused.",
};

describe("VideoPipelineResultNotice", () => {
  it("labels working controller states clearly", () => {
    const result: PipelineResult = {
      ...baseResult,
      controller_status: "planning",
      controller_status_category: "working",
      controller_status_detail: "Generating the first edit plan.",
    };

    const markup = renderToStaticMarkup(
      <VideoPipelineResultNotice apiBase="http://localhost:10000" result={result} />
    );

    expect(getControllerStatusLabel(result)).toBe("Working");
    expect(markup).toContain("Working - planning - Generating the first edit plan.");
    expect(markup).not.toContain("Complete - planning");
  });

  it("labels awaiting user input states clearly", () => {
    const result: PipelineResult = {
      ...baseResult,
      controller_status: "awaiting_user_input",
      controller_status_category: "waiting_for_user_input",
      controller_status_detail: "Need clarification on the edit priority.",
    };

    const markup = renderToStaticMarkup(
      <VideoPipelineResultNotice apiBase="http://localhost:10000" result={result} />
    );

    expect(getControllerStatusLabel(result)).toBe("Awaiting User Input");
    expect(markup).toContain("Awaiting User Input - awaiting_user_input");
  });

  it("does not mislabel blocked jobs as complete", () => {
    const result: PipelineResult = {
      ...baseResult,
      controller_status: "blocked_by_unapplied_edits",
      controller_status_category: "blocked",
      controller_status_detail: "Pending edits must be applied before rendering.",
    };

    const markup = renderToStaticMarkup(
      <VideoPipelineResultNotice apiBase="http://localhost:10000" result={result} />
    );

    expect(getControllerStatusLabel(result)).toBe("Blocked");
    expect(markup).toContain("Blocked - blocked_by_unapplied_edits");
    expect(markup).not.toContain("Complete - blocked_by_unapplied_edits");
  });

  it("labels failed jobs as failed", () => {
    const result: PipelineResult = {
      ...baseResult,
      controller_status: "failed",
      controller_status_category: "failed",
      controller_status_detail: "Render provider timed out.",
      error: "Render provider timed out.",
    };

    const markup = renderToStaticMarkup(
      <VideoPipelineResultNotice apiBase="http://localhost:10000" result={result} />
    );

    expect(getControllerStatusLabel(result)).toBe("Failed");
    expect(markup).toContain("Failed - failed - Render provider timed out.");
  });

  it("labels finished jobs as complete", () => {
    const result: PipelineResult = {
      success: true,
      controller_status: "finished",
      controller_status_category: "complete",
      controller_status_detail: "Render complete.",
      url: "https://example.test/render.mp4",
      preview_url: "/files/job/output.mp4",
    };

    const markup = renderToStaticMarkup(
      <VideoPipelineResultNotice apiBase="http://localhost:10000" result={result} />
    );

    expect(getControllerStatusLabel(result)).toBe("Complete");
    expect(markup).toContain("Complete - finished - Render complete.");
    expect(markup).toContain("http://localhost:10000/files/job/output.mp4");
  });
});
