import React, { useState } from "react";
import { motion } from "framer-motion";
import { Play, Download, Share2, ExternalLink } from "lucide-react";
import { PipelineResult } from "./VideoPipelinePanel";

interface ResultPreviewCardProps {
  result: PipelineResult;
  apiBase: string;
}

const toAbsoluteUrl = (apiBase: string, value?: string | null): string => {
  if (!value) return "";
  if (value.startsWith("/")) return `${apiBase}${value}`;
  return value;
};

const getPreviewUrl = (apiBase: string, value?: string | null): string =>
  toAbsoluteUrl(apiBase, value);

export const ResultPreviewCard: React.FC<ResultPreviewCardProps> = ({ result, apiBase }) => {
  const [isVideoLoaded, setIsVideoLoaded] = useState(false);
  const [showFullScreen, setShowFullScreen] = useState(false);

  const previewTarget = getPreviewUrl(apiBase, result.preview_url) || result.url;

  if (!previewTarget) {
    return null;
  }

  return (
    <>
      <motion.div
        className="panel overflow-hidden"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-700/50">
          <h3 className="text-sm font-semibold text-gray-100">Rendered Preview</h3>
          <p className="text-xs text-gray-500 mt-1">Your video is ready for review</p>
        </div>

        {/* Video Container */}
        <div className="relative bg-black/50 aspect-video overflow-hidden">
          <motion.div
            className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-purple-500/10"
            initial={{ opacity: 0 }}
            animate={{ opacity: isVideoLoaded ? 0 : 1 }}
            transition={{ duration: 0.3 }}
          />

          {/* Video Element */}
          <video
            className="w-full h-full object-cover"
            src={previewTarget}
            controls
            preload="metadata"
            onLoadedMetadata={() => setIsVideoLoaded(true)}
          />

          {/* Play Button Overlay (when not loaded) */}
          {!isVideoLoaded && (
            <motion.div
              className="absolute inset-0 flex items-center justify-center bg-black/30 backdrop-blur-sm"
              initial={{ opacity: 1 }}
              animate={{ opacity: 0 }}
              transition={{ duration: 0.5, delay: 0.5 }}
              style={{ pointerEvents: "none" }}
            >
              <motion.div
                animate={{ scale: [1, 1.1, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <div className="w-16 h-16 rounded-full bg-blue-500/30 border-2 border-blue-400 flex items-center justify-center">
                  <Play size={28} className="text-blue-300 ml-1" fill="currentColor" />
                </div>
              </motion.div>
            </motion.div>
          )}
        </div>

        {/* Actions */}
        <div className="px-6 py-4 border-t border-gray-700/50 flex gap-2">
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
            onClick={() => setShowFullScreen(true)}
            className="flex-1 btn btn-secondary text-xs justify-center"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Play size={14} />
            Fullscreen
          </motion.button>
        </div>

        {/* Metadata */}
        <div className="px-6 py-3 bg-gray-900/30 text-xs space-y-1">
          {result.render_id && (
            <p className="text-gray-500">
              <span className="text-gray-400">Render ID:</span>{" "}
              <span className="font-mono text-gray-300">{result.render_id}</span>
            </p>
          )}
          {result.intent_mode && (
            <p className="text-gray-500">
              <span className="text-gray-400">Format:</span>{" "}
              <span className="capitalize text-gray-300">{result.intent_mode}</span>
            </p>
          )}
        </div>
      </motion.div>

      {/* Fullscreen Modal */}
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
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0.9 }}
            onClick={(e) => e.stopPropagation()}
          >
            <video
              className="w-full h-full object-contain"
              src={previewTarget}
              controls
              autoPlay
            />
          </motion.div>

          {/* Close Button */}
          <motion.button
            className="absolute top-4 right-4 p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white"
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setShowFullScreen(false)}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </motion.button>
        </motion.div>
      )}
    </>
  );
};
