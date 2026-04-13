import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

export const HeroHeader: React.FC = () => {
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.2,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.6, ease: "easeOut" as any },
    },
  };

  return (
    <section className="relative overflow-hidden pt-24 pb-16">
      {/* Animated Background Gradient */}
      <div className="absolute inset-0 -z-10">
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at 30% 50%, oklch(0.75 0.18 70 / 0.12) 0%, transparent 60%)",
          }}
        />
        <motion.div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at 70% 30%, oklch(0.55 0.22 255 / 0.08) 0%, transparent 50%)",
          }}
          animate={{
            opacity: [0.5, 1, 0.5],
          }}
          transition={{
            duration: 6,
            repeat: Infinity,
            ease: "easeInOut" as any,
          }}
        />
      </div>

      {/* Content */}
      <div className="container mx-auto px-6 max-w-7xl relative z-10">
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          {/* Section Number */}
          <motion.span
            className="section-number block mb-4"
            variants={itemVariants}
          >
            Pipeline Control
          </motion.span>

          {/* Main Title */}
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

          {/* Subtitle */}
          <motion.p
            className="text-sm md:text-base max-w-2xl"
            style={{
              color: "oklch(0.55 0.01 80)",
              fontFamily: "'DM Sans', sans-serif",
            }}
            variants={itemVariants}
          >
            Transform your video ideas into polished productions. Submit sources, refine your
            creative brief with AI assistance, and render professional edits end-to-end.
          </motion.p>

          {/* Accent Line */}
          <motion.div
            className="amber-divider mt-6 w-24"
            variants={itemVariants}
          />

          {/* Feature Badges */}
          <motion.div
            className="flex flex-wrap gap-3 mt-8"
            variants={itemVariants}
          >
            {[
              { icon: "🎬", label: "Multi-Source" },
              { icon: "🤖", label: "AI Brief" },
              { icon: "⚡", label: "Live Status" },
              { icon: "📤", label: "YouTube Ready" },
            ].map((feature, idx) => (
              <motion.div
                key={idx}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/30 text-xs font-medium text-blue-300"
                whileHover={{ scale: 1.05, backgroundColor: "rgba(59, 130, 246, 0.2)" }}
              >
                <span>{feature.icon}</span>
                <span>{feature.label}</span>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      </div>

      {/* Decorative Elements */}
      <motion.div
        className="absolute top-10 right-10 opacity-20"
        animate={{ rotate: 360 }}
        transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
      >
        <Sparkles size={32} className="text-amber-400" />
      </motion.div>
    </section>
  );
};
