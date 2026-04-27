import React from "react";
import { useState } from "react";
import { motion } from "framer-motion";
import { ExternalLink, Play } from "lucide-react";

import type { PipelineResult } from "./VideoPipelinePanel";

interface ResultPreviewCardProps {
  result: PipelineResult;
  apiBase: string;
}

const toAbsoluteUrl = (apiBase: string, value?: string | null): string => {
  if (!value) return "";
  if (value.startsWith("/")) return `${apiBase}${value}`;
  return value;
};

export const ResultPreviewCard: React.FC<ResultPreviewCardProps> = ({
  result,
  apiBase,
}) => {
  const [isVideoLoaded, setIsVideoLoaded] = useState(false);
  const [showFullScreen, setShowFullScreen] = useState(false);
  const previewTarget =
    toAbsoluteUrl(apiBase, result.preview_url) || result.url || "";

  if (!previewTarget) {
    return null;
  }

  return (
    <>
      <motion.div
        className="panel overflow-hidden"
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.45, delay: 0.15 }}
      >
        <div className="px-6 py-4 border-b border-slate-700/50">
          <h3 className="text-sm font-semibold text-slate-100">Rendered Preview</h3>
          <p className="text-xs text-slate-500 mt-1">
            Review the latest output before publishing.
          </p>
        </div>

        <div className="relative bg-black/50 aspect-video overflow-hidden">
          <motion.div
            className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-purple-500/10"
            initial={{ opacity: 0 }}
            animate={{ opacity: isVideoLoaded ? 0 : 1 }}
            transition={{ duration: 0.3 }}
          />

          <video
            className="w-full h-full object-cover"
            src={previewTarget}
            controls
            preload="metadata"
            onLoadedMetadata={() => setIsVideoLoaded(true)}
          />

          {!isVideoLoaded && (
            <motion.div
              className="absolute inset-0 flex items-center justify-center bg-black/30 backdrop-blur-sm"
              initial={{ opacity: 1 }}
              animate={{ opacity: 0 }}
              transition={{ duration: 0.45, delay: 0.45 }}
              style={{ pointerEvents: "none" }}
            >
              <motion.div
                animate={{ scale: [1, 1.08, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <div className="w-16 h-16 rounded-full bg-blue-500/30 border-2 border-blue-400 flex items-center justify-center">
                  <Play size={28} className="text-blue-300 ml-1" fill="currentColor" />
                </div>
              </motion.div>
            </motion.div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-slate-700/50 flex gap-2">
          <motion.a
            href={previewTarget}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 btn btn-secondary text-xs justify-center"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <ExternalLink size={14} />
            Open in New Tab
          </motion.a>

          <motion.button
            type="button"
            onClick={() => setShowFullScreen(true)}
            className="flex-1 btn btn-secondary text-xs justify-center"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Play size={14} />
            Fullscreen
          </motion.button>
        </div>

        <div className="px-6 py-3 bg-slate-900/30 text-xs space-y-1">
          {result.render_id && (
            <p className="text-slate-500">
              <span className="text-slate-400">Render ID:</span>{" "}
              <span className="font-mono text-slate-300">{result.render_id}</span>
            </p>
          )}
          {result.intent_mode && (
            <p className="text-slate-500">
              <span className="text-slate-400">Format:</span>{" "}
              <span className="capitalize text-slate-300">{result.intent_mode}</span>
            </p>
          )}
        </div>
      </motion.div>

      {showFullScreen && (
        <motion.div
          className="fixed inset-0 z-50 bg-black/95 flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={() => setShowFullScreen(false)}
        >
          <motion.div
            className="w-full h-full flex items-center justify-center p-4"
            initial={{ scale: 0.94 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0.94 }}
            onClick={(e) => e.stopPropagation()}
          >
            <video
              className="w-full h-full object-contain"
              src={previewTarget}
              controls
              autoPlay
            />
          </motion.div>

          <motion.button
            type="button"
            className="absolute top-4 right-4 p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white"
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.96 }}
            onClick={() => setShowFullScreen(false)}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </motion.button>
        </motion.div>
      )}
    </>
  );
};
