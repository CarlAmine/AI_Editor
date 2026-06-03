import { EmptyState } from "./EmptyState";
import { LoadingIndicator } from "./LoadingIndicator";
import { AssistantMessageCard } from "./AssistantMessageCard";
import { UserMessageCard } from "./UserMessageCard";
import { StyleSummaryCard } from "./StyleSummaryCard";
import { SlotReplacementForm } from "./SlotReplacementForm";
import { TextReplacementForm } from "./TextReplacementForm";
import { RenderStatusCard } from "./RenderStatusCard";
import { ResultPreviewCard } from "../ResultPreviewCard";
import type { useWorkspaceChat } from "../../hooks/useWorkspaceChat";
import type { SlotMappingEntry, TextReplacementEntry } from "../../types/pipeline";
import type { PipelineResult } from "../VideoPipelinePanel";

type ChatApi = ReturnType<typeof useWorkspaceChat>;

type Props = ChatApi & {
  chatState: Record<string, unknown>;
  displayResult?: PipelineResult | null;
  apiBase?: string;
};

export function ConversationCanvas({
  messages,
  isLoading,
  chatWindowRef,
  currentState,
  updateState,
  shouldShowFinalPlan,
  isPipelineSubmitting,
  handleConfirmAndRender,
  handleEditPlan,
  finalReport,
  chatState,
  updateMessageCompletion,
  displayResult,
  apiBase = "",
}: Props) {
  const summary = chatState.reference_analysis as
    | {
        durationSeconds: number;
        fps: number;
        width: number;
        height: number;
        aspectRatio: string;
        sceneCount: number;
        styleSummary: string;
      }
    | undefined;
  const slots = Array.isArray(chatState.reference_slots)
    ? (chatState.reference_slots as Array<{
        slot_id?: number;
        slotId?: number;
        role?: string;
        start_time?: number;
        end_time?: number;
        duration?: number;
        description?: string;
      }>)
    : [];
  const slotRows = Array.isArray(chatState.slot_mapping)
    ? (chatState.slot_mapping as SlotMappingEntry[])
    : [];
  const textReplacements = Array.isArray(chatState.text_replacements)
    ? (chatState.text_replacements as TextReplacementEntry[])
    : [];
  const textMoments = Array.isArray(chatState.text_moments)
    ? chatState.text_moments
    : [];
  const sameTargetVideo = Boolean(chatState.use_same_target_video_for_all_slots);
  const sharedTargetVideoUrl = String(chatState.shared_target_video_url || "");
  const hasReference = Boolean(summary && slots.length > 0);

  const updateSlotRows = (nextRows: SlotMappingEntry[]) => {
    updateState({
      ...currentState,
      slot_mapping: nextRows,
    });
  };

  const updateTextRows = (nextRows: TextReplacementEntry[]) => {
    updateState({
      ...currentState,
      text_replacements: nextRows,
      text_overlays: nextRows.map((row) => ({
        overlay_id: row.id,
        slot_id: row.slotId ?? null,
        start: row.start,
        end: row.end,
        detected_text: row.detectedText,
        render_text: row.action === "remove" ? "" : row.text,
        action: row.action === "replace" ? "render" : row.action,
      })),
      ready_to_submit: false,
    });
  };

  const handleSlotContinue = () => {
    updateState({
      ...currentState,
      phase: textMoments.length > 0 ? "awaiting_text_overlays" : "awaiting_final_confirmation",
      ready_to_submit: textMoments.length === 0,
    });
  };

  const handleTextContinue = () => {
    updateState({
      ...currentState,
      phase: "awaiting_final_confirmation",
      ready_to_submit: true,
      text_overlays_resolved: true,
    });
  };

  const clearSlots = () => {
    updateState({
      ...currentState,
      slot_mapping: slots.map((slot) => ({
        slot_id: Number(slot.slot_id ?? slot.slotId),
        clip_id: `slot_${Number(slot.slot_id ?? slot.slotId)}`,
        clip_url: "",
        source_start: 0,
        source_end: Number(slot.duration ?? 0),
      })),
      use_same_target_video_for_all_slots: false,
      shared_target_video_url: "",
      ready_to_submit: false,
    });
  };

  const clearText = () => {
    updateState({
      ...currentState,
      text_replacements: textMoments.map((moment: Record<string, unknown>, index: number) => ({
        id: String(moment.id || moment.overlay_id || `text_${index + 1}`),
        start: Number(moment.start ?? 0),
        end: Number(moment.end ?? 0),
        detectedText: String(moment.detectedText || moment.detected_text || ""),
        action: "keep",
        text: String(moment.detectedText || moment.detected_text || ""),
        slotId: moment.slotId ?? moment.slot_id ?? null,
      })),
      ready_to_submit: false,
      text_overlays_resolved: false,
    });
  };

  return (
    <div className="workspace-conversation">
      <div className="workspace-conversation-scroll" ref={chatWindowRef}>
        <div className="workspace-conversation-stack">
          {messages.length === 0 && !hasReference && <EmptyState />}

          {messages.map((message) =>
            message.from === "user" ? (
              <UserMessageCard key={message.id} text={message.text} timestamp={message.timestamp} />
            ) : (
              <AssistantMessageCard
                key={message.id}
                id={message.id}
                text={message.text}
                timestamp={message.timestamp}
                streaming={Boolean(message.streaming)}
                onStreamComplete={updateMessageCompletion}
              />
            ),
          )}

          {isLoading && <LoadingIndicator />}

          {hasReference && summary && (
            <StyleSummaryCard
              summary={{
                durationSeconds: Number(summary.durationSeconds || 0),
                fps: Number(summary.fps || 0),
                width: Number(summary.width || 0),
                height: Number(summary.height || 0),
                aspectRatio: String(summary.aspectRatio || "16:9"),
                sceneCount: Number(summary.sceneCount || slots.length),
                styleSummary: String(summary.styleSummary || ""),
              }}
              slots={slots.map((slot) => ({
                slotId: Number(slot.slotId ?? slot.slot_id),
                role: String(slot.role || "b-roll"),
                start: Number(slot.start_time ?? 0),
                end: Number(slot.end_time ?? 0),
                duration: Number(slot.duration ?? 0),
                description: String(slot.description || ""),
              }))}
            />
          )}

          {hasReference && (
            <SlotReplacementForm
              slots={slots.map((slot) => ({
                slotId: Number(slot.slotId ?? slot.slot_id),
                role: String(slot.role || "b-roll"),
                start: Number(slot.start_time ?? 0),
                end: Number(slot.end_time ?? 0),
                duration: Number(slot.duration ?? 0),
                description: String(slot.description || ""),
              }))}
              slotMapping={slotRows}
              sameTargetVideo={sameTargetVideo}
              sharedTargetVideoUrl={sharedTargetVideoUrl}
              onChange={updateSlotRows}
              onToggleSameTargetVideo={(enabled) =>
                updateState({
                  ...currentState,
                  use_same_target_video_for_all_slots: enabled,
                  shared_target_video_url: enabled
                    ? sharedTargetVideoUrl || String(slotRows[0]?.clip_url || "")
                    : "",
                  slot_mapping: slotRows.map((row, index) => ({
                    ...row,
                    clip_url: enabled
                      ? String(sharedTargetVideoUrl || row.clip_url || "")
                      : row.clip_url,
                    clip_id: row.clip_id || `slot_${row.slot_id || index + 1}`,
                  })),
                })
              }
              onSharedTargetVideoUrlChange={(url) =>
                updateState({
                  ...currentState,
                  shared_target_video_url: url,
                  slot_mapping: slotRows.map((row) => ({
                    ...row,
                    clip_url: url,
                  })),
                })
              }
              onContinue={handleSlotContinue}
              onClear={clearSlots}
            />
          )}

          {hasReference && textMoments.length > 0 && (
            <TextReplacementForm
              rows={textReplacements}
              onChange={updateTextRows}
              onContinue={handleTextContinue}
              onClear={clearText}
            />
          )}

          {shouldShowFinalPlan && (
            <RenderStatusCard
              state={currentState}
              onConfirm={handleConfirmAndRender}
              onEdit={handleEditPlan}
              isSubmitting={isPipelineSubmitting}
            />
          )}

          {finalReport && (
            <article className="workspace-msg-assistant">
              <div className="workspace-msg-meta">Final brief</div>
              <div className="workspace-card workspace-message-card" style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {finalReport}
              </div>
            </article>
          )}

          {displayResult?.success && (displayResult.preview_url || displayResult.url) && (
            <article className="workspace-msg-assistant" style={{ maxWidth: "min(90%, 520px)" }}>
              <div className="workspace-msg-meta">Rendered video</div>
              <ResultPreviewCard result={displayResult} apiBase={apiBase} />
            </article>
          )}
        </div>
      </div>
    </div>
  );
}
