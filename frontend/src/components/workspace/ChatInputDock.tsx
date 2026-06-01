import { Send } from "lucide-react";
import type { FormEvent, KeyboardEvent } from "react";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (e: FormEvent) => void;
  onKeyDown: (e: KeyboardEvent<HTMLTextAreaElement>) => void;
  disabled?: boolean;
};

export function ChatInputDock({ value, onChange, onSubmit, onKeyDown, disabled }: Props) {
  return (
    <div className="workspace-input-dock">
      <form className="workspace-input-dock-inner" onSubmit={onSubmit}>
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Describe your edit, paste a reference URL, or ask about status..."
          rows={1}
          disabled={disabled}
        />
        <button type="submit" className="workspace-send-btn" disabled={disabled || !value.trim()}>
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}
