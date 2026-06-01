import { StreamingText } from "./StreamingText";

type Props = {
  id: string;
  text: string;
  timestamp: Date;
  streaming?: boolean;
  onStreamComplete?: (messageId: string) => void;
};

export function AssistantMessageCard({ id, text, timestamp, streaming = false, onStreamComplete }: Props) {
  return (
    <article className="workspace-msg-assistant">
      <div className="workspace-msg-meta">
        Assistant - {timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </div>
      <div className="workspace-card workspace-message-card">
        {streaming ? (
          <StreamingText messageId={id} text={text} speedMs={24} onComplete={onStreamComplete} />
        ) : (
          text
        )}
      </div>
    </article>
  );
}
