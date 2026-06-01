export type ResumeTarget = {
  endpoint: string;
  isResume: boolean;
};

export function resolveChatSubmitTarget(
  apiBase: string,
  jobStatusCategory?: string | null,
  jobId?: string | null
): ResumeTarget {
  if (
    jobId &&
    (jobStatusCategory === "waiting_for_user_input" || jobStatusCategory === "blocked")
  ) {
    return {
      endpoint: `${apiBase}/jobs/${jobId}/resume`,
      isResume: true,
    };
  }
  return {
    endpoint: `${apiBase}/chat`,
    isResume: false,
  };
}
