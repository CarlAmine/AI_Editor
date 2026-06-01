import { useEffect, useMemo, useRef, useState } from "react";

const completedStreamingMessageIds = new Set<string>();

type Props = {
  messageId: string;
  text: string;
  speedMs?: number;
  onComplete?: (messageId: string) => void;
};

function usePrefersReducedMotion() {
  return useMemo(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return false;
    }
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);
}

export function StreamingText({ messageId, text, speedMs = 28, onComplete }: Props) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const words = useMemo(() => text.split(/\s+/).filter(Boolean), [text]);
  const shouldAnimate = !prefersReducedMotion && !completedStreamingMessageIds.has(messageId);
  const [visibleWordCount, setVisibleWordCount] = useState(shouldAnimate ? 1 : words.length);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!shouldAnimate) {
      setVisibleWordCount(words.length);
      return;
    }

    if (completedStreamingMessageIds.has(messageId)) {
      setVisibleWordCount(words.length);
      return;
    }

    setVisibleWordCount(1);
    timerRef.current = window.setTimeout(function tick() {
      setVisibleWordCount((current) => {
        const next = Math.min(current + 1, words.length);
        if (next >= words.length) {
          completedStreamingMessageIds.add(messageId);
          onComplete?.(messageId);
        } else {
          timerRef.current = window.setTimeout(tick, speedMs);
        }
        return next;
      });
    }, speedMs);

    return () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [messageId, onComplete, shouldAnimate, speedMs, words.length]);

  useEffect(() => {
    if (prefersReducedMotion) {
      completedStreamingMessageIds.add(messageId);
      onComplete?.(messageId);
    }
  }, [messageId, onComplete, prefersReducedMotion]);

  const visibleText = useMemo(() => words.slice(0, visibleWordCount).join(" "), [visibleWordCount, words]);

  return (
    <span aria-live="polite" aria-atomic="true">
      {visibleText}
    </span>
  );
}
