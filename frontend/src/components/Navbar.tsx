/* ============================================================
   Navbar — Cinematic Dark Editorial
   Fixed top navigation with amber accent and film-strip logo
   ============================================================ */

import { useState, useEffect } from "react";
import { Link, useLocation } from "wouter";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Github, Film } from "lucide-react";

const navLinks = [
  { href: "/", label: "Home" },
  { href: "/about", label: "About" },
  { href: "/features", label: "Features" },
  { href: "/architecture", label: "Architecture" },
  { href: "/stack", label: "Tech Stack" },
  { href: "/docs", label: "Docs" },
  { href: "/pipeline", label: "Pipeline" },
];

export default function Navbar() {
  const [location] = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [location]);

  return (
    <>
      <motion.nav
        initial={{ y: -80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.1 }}
        className="fixed top-0 left-0 right-0 z-40 transition-all duration-300"
        style={{
          background: scrolled
            ? "oklch(0.09 0.015 265 / 0.95)"
            : "oklch(0.09 0.015 265 / 0.6)",
          backdropFilter: "blur(16px)",
          borderBottom: scrolled ? "1px solid oklch(1 0 0 / 8%)" : "1px solid transparent",
          boxShadow: scrolled ? "0 4px 30px oklch(0 0 0 / 0.4)" : "none",
        }}
      >
        <div className="container mx-auto px-6 h-16 flex items-center justify-between max-w-7xl">
          {/* Logo */}
          <Link href="/">
            <div className="flex items-center gap-2.5 group">
              <div className="relative">
                <Film
                  size={22}
                  style={{ color: "oklch(0.75 0.18 70)" }}
                  className="group-hover:scale-110 transition-transform duration-200"
                />
                <div
                  className="absolute inset-0 blur-md opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                  style={{ background: "oklch(0.75 0.18 70 / 0.4)" }}
                />
              </div>
              <span
                className="text-xl tracking-widest"
                style={{
                  fontFamily: "'Bebas Neue', sans-serif",
                  background: "linear-gradient(135deg, oklch(0.85 0.18 75), oklch(0.65 0.18 60))",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                AI EDITOR
              </span>
            </div>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => {
              const isActive = location === link.href;
              return (
                <Link key={link.href} href={link.href}>
                  <div
                    className="relative px-4 py-2 text-sm font-medium tracking-wide transition-colors duration-200 rounded-sm"
                    style={{
                      fontFamily: "'DM Sans', sans-serif",
                      color: isActive
                        ? "oklch(0.75 0.18 70)"
                        : "oklch(0.65 0.01 80)",
                    }}
                  >
                    <span className="relative z-10 hover:text-[oklch(0.93_0.01_80)] transition-colors duration-200">
                      {link.label}
                    </span>
                    {isActive && (
                      <motion.div
                        layoutId="nav-indicator"
                        className="absolute bottom-0 left-3 right-3 h-px"
                        style={{ background: "oklch(0.75 0.18 70)" }}
                        transition={{ type: "spring", stiffness: 400, damping: 30 }}
                      />
                    )}
                  </div>
                </Link>
              );
            })}
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-3">
            <a
              href="https://github.com/CarlAmine/AI_Editor"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden md:flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-sm transition-all duration-200"
              style={{
                fontFamily: "'DM Sans', sans-serif",
                border: "1px solid oklch(0.75 0.18 70 / 0.4)",
                color: "oklch(0.75 0.18 70)",
                background: "oklch(0.75 0.18 70 / 0.05)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "oklch(0.75 0.18 70 / 0.15)";
                e.currentTarget.style.borderColor = "oklch(0.75 0.18 70 / 0.8)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "oklch(0.75 0.18 70 / 0.05)";
                e.currentTarget.style.borderColor = "oklch(0.75 0.18 70 / 0.4)";
              }}
            >
              <Github size={15} />
              GitHub
            </a>

            {/* Mobile menu toggle */}
            <button
              className="md:hidden p-2 rounded-sm transition-colors duration-200"
              style={{ color: "oklch(0.75 0.18 70)" }}
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Toggle menu"
            >
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
      </motion.nav>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="fixed top-16 left-0 right-0 z-30 md:hidden"
            style={{
              background: "oklch(0.09 0.015 265 / 0.98)",
              backdropFilter: "blur(20px)",
              borderBottom: "1px solid oklch(1 0 0 / 8%)",
            }}
          >
            <div className="container mx-auto px-6 py-4 flex flex-col gap-1">
              {navLinks.map((link, i) => {
                const isActive = location === link.href;
                return (
                  <motion.div
                    key={link.href}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                  >
                    <Link href={link.href}>
                      <div
                        className="px-4 py-3 text-sm font-medium tracking-wide rounded-sm transition-colors duration-200"
                        style={{
                          fontFamily: "'DM Sans', sans-serif",
                          color: isActive ? "oklch(0.75 0.18 70)" : "oklch(0.65 0.01 80)",
                          background: isActive ? "oklch(0.75 0.18 70 / 0.08)" : "transparent",
                          borderLeft: isActive ? "2px solid oklch(0.75 0.18 70)" : "2px solid transparent",
                        }}
                      >
                        {link.label}
                      </div>
                    </Link>
                  </motion.div>
                );
              })}
              <div className="mt-2 pt-3" style={{ borderTop: "1px solid oklch(1 0 0 / 8%)" }}>
                <a
                  href="https://github.com/CarlAmine/AI_Editor"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-4 py-3 text-sm font-medium"
                  style={{ color: "oklch(0.75 0.18 70)", fontFamily: "'DM Sans', sans-serif" }}
                >
                  <Github size={15} />
                  View on GitHub
                </a>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
