/* ============================================================
   PageLoader — Cinematic Dark Editorial
   Full-screen loading animation with pipeline stages
   ============================================================ */

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface PageLoaderProps {
  onComplete: () => void;
}

const stages = [
  "Initializing pipeline...",
  "Loading AI modules...",
  "Connecting to Shotstack...",
  "Ready.",
];

export default function PageLoader({ onComplete }: PageLoaderProps) {
  const [progress, setProgress] = useState(0);
  const [stageIndex, setStageIndex] = useState(0);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        const next = prev + 2;
        if (next >= 100) {
          clearInterval(interval);
          setTimeout(() => {
            setDone(true);
            setTimeout(onComplete, 500);
          }, 300);
          return 100;
        }
        return next;
      });
    }, 20);
    return () => clearInterval(interval);
  }, [onComplete]);

  useEffect(() => {
    if (progress < 30) setStageIndex(0);
    else if (progress < 60) setStageIndex(1);
    else if (progress < 90) setStageIndex(2);
    else setStageIndex(3);
  }, [progress]);

  return (
    <AnimatePresence>
      {!done && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center"
          style={{ background: "oklch(0.09 0.015 265)" }}
        >
          {/* Background subtle grid */}
          <div
            className="absolute inset-0 opacity-5"
            style={{
              backgroundImage: `linear-gradient(oklch(0.75 0.18 70 / 0.3) 1px, transparent 1px), linear-gradient(90deg, oklch(0.75 0.18 70 / 0.3) 1px, transparent 1px)`,
              backgroundSize: "60px 60px",
            }}
          />

          {/* Logo area */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="relative z-10 text-center mb-12"
          >
            {/* Film strip icon */}
            <div className="flex items-center justify-center gap-3 mb-4">
              <div className="flex gap-1">
                {[...Array(4)].map((_, i) => (
                  <motion.div
                    key={i}
                    className="w-3 h-5 rounded-sm"
                    style={{ background: "oklch(0.75 0.18 70)" }}
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.15 }}
                  />
                ))}
              </div>
              <div
                className="w-2 h-2 rounded-full"
                style={{ background: "oklch(0.55 0.22 255)" }}
              />
              <div className="flex gap-1">
                {[...Array(4)].map((_, i) => (
                  <motion.div
                    key={i}
                    className="w-3 h-5 rounded-sm"
                    style={{ background: "oklch(0.75 0.18 70)" }}
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1.2, repeat: Infinity, delay: (i + 4) * 0.15 }}
                  />
                ))}
              </div>
            </div>

            <h1
              className="text-6xl md:text-8xl tracking-widest"
              style={{
                fontFamily: "'Bebas Neue', sans-serif",
                background: "linear-gradient(135deg, oklch(0.85 0.18 75), oklch(0.65 0.18 60))",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              AI EDITOR
            </h1>
            <p
              className="text-sm tracking-[0.3em] mt-2 uppercase"
              style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.55 0.22 255)" }}
            >
              Intelligent Video Pipeline
            </p>
          </motion.div>

          {/* Progress section */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4, duration: 0.4 }}
            className="relative z-10 w-full max-w-sm px-8"
          >
            {/* Stage label */}
            <div className="flex justify-between items-center mb-3">
              <AnimatePresence mode="wait">
                <motion.span
                  key={stageIndex}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 10 }}
                  transition={{ duration: 0.2 }}
                  className="text-xs tracking-widest uppercase"
                  style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.55 0.01 80)" }}
                >
                  {stages[stageIndex]}
                </motion.span>
              </AnimatePresence>
              <span
                className="text-xs"
                style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.75 0.18 70)" }}
              >
                {progress}%
              </span>
            </div>

            {/* Progress bar track */}
            <div
              className="h-px w-full rounded-full overflow-hidden"
              style={{ background: "oklch(1 0 0 / 10%)" }}
            >
              <motion.div
                className="h-full rounded-full"
                style={{
                  background: "linear-gradient(90deg, oklch(0.75 0.18 70), oklch(0.55 0.22 255))",
                  width: `${progress}%`,
                  boxShadow: "0 0 10px oklch(0.75 0.18 70 / 0.8)",
                }}
                transition={{ duration: 0.1 }}
              />
            </div>

            {/* Pipeline stage dots */}
            <div className="flex justify-between mt-4">
              {stages.map((_, i) => (
                <motion.div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full"
                  style={{
                    background:
                      i <= stageIndex
                        ? "oklch(0.75 0.18 70)"
                        : "oklch(1 0 0 / 15%)",
                    boxShadow: i <= stageIndex ? "0 0 6px oklch(0.75 0.18 70 / 0.8)" : "none",
                  }}
                  animate={i === stageIndex ? { scale: [1, 1.4, 1] } : {}}
                  transition={{ duration: 0.6, repeat: Infinity }}
                />
              ))}
            </div>
          </motion.div>

          {/* Scanning line */}
          <motion.div
            className="absolute left-0 right-0 h-px"
            style={{ background: "oklch(0.75 0.18 70 / 0.3)", top: "50%" }}
            animate={{ opacity: [0, 0.5, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
