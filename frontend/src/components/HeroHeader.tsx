import React from "react";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

export const HeroHeader: React.FC = () => {
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.15,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 18 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.55, ease: "easeOut" as const },
    },
  };

  return (
    <section className="hero-header relative overflow-hidden pt-24 pb-16">
      <div className="absolute inset-0 -z-10">
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at 24% 42%, oklch(0.75 0.18 70 / 0.14) 0%, transparent 58%)",
          }}
        />
        <motion.div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at 76% 28%, oklch(0.55 0.22 255 / 0.08) 0%, transparent 48%)",
          }}
          animate={{ opacity: [0.45, 1, 0.45] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>

      <div className="container mx-auto max-w-7xl px-6 relative z-10">
        <motion.div variants={containerVariants} initial="hidden" animate="visible">
          <motion.span className="section-number block mb-4" variants={itemVariants}>
            Pipeline Control
          </motion.span>

          <motion.h1
            className="text-6xl md:text-7xl leading-none mb-6 font-bold"
            style={{
              fontFamily: "'Bebas Neue', sans-serif",
              background:
                "linear-gradient(160deg, oklch(0.95 0.01 80) 0%, oklch(0.75 0.18 70) 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
            variants={itemVariants}
          >
            Mission Control
          </motion.h1>

          <motion.p
            className="text-sm md:text-base max-w-2xl"
            style={{
              color: "oklch(0.55 0.01 80)",
              fontFamily: "'DM Sans', sans-serif",
            }}
            variants={itemVariants}
          >
            Transform video ideas into polished productions. Configure sources,
            refine the brief with AI assistance, monitor controller status live,
            and ship a finished edit without leaving the page.
          </motion.p>

          <motion.div className="amber-divider mt-6 w-24" variants={itemVariants} />
        </motion.div>
      </div>

      <motion.div
        className="absolute top-10 right-10 opacity-20"
        animate={{ rotate: 360 }}
        transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
      >
        <Sparkles size={32} className="text-amber-400" />
      </motion.div>
    </section>
  );
};
