type Props = {
  text: string;
  timestamp: Date;
};

export function UserMessageCard({ text, timestamp }: Props) {
  return (
    <article style={{ marginBottom: 20 }}>
      <div className="workspace-msg-meta" style={{ textAlign: "right" }}>
        You - {timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </div>
      <div className="workspace-msg-user">{text}</div>
    </article>
  );
}
