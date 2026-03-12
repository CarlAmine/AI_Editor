/* ============================================================
   AI EDITOR SHOWCASE — Multi-page app with functional pipeline
   Design: Cinematic Dark Editorial
   Routes: Home, About, Features, Architecture, Tech Stack, Docs, Pipeline
   ============================================================ */

import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch, useLocation } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import { AnimatePresence, motion } from "framer-motion";
import Home from "./pages/Home";
import About from "./pages/About";
import Features from "./pages/Features";
import Architecture from "./pages/Architecture";
import Stack from "./pages/Stack";
import Docs from "./pages/Docs";
import Pipeline from "./pages/Pipeline";
import Navbar from "./components/Navbar";
import PageLoader from "./components/PageLoader";
import { useState, useEffect } from "react";

const pageVariants = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4 } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.25 } },
};

function AnimatedRoute({ component: Component }: { component: React.ComponentType }) {
  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      style={{ minHeight: "100vh" }}
    >
      <Component />
    </motion.div>
  );
}

function Router() {
  const [location] = useLocation();
  return (
    <AnimatePresence mode="wait">
      <Switch key={location} location={location}>
        <Route path="/" component={() => <AnimatedRoute component={Home} />} />
        <Route path="/about" component={() => <AnimatedRoute component={About} />} />
        <Route path="/features" component={() => <AnimatedRoute component={Features} />} />
        <Route path="/architecture" component={() => <AnimatedRoute component={Architecture} />} />
        <Route path="/stack" component={() => <AnimatedRoute component={Stack} />} />
        <Route path="/docs" component={() => <AnimatedRoute component={Docs} />} />
        <Route path="/pipeline" component={() => <AnimatedRoute component={Pipeline} />} />
        <Route component={NotFound} />
      </Switch>
    </AnimatePresence>
  );
}

function App() {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 2200);
    return () => clearTimeout(timer);
  }, []);

  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="dark">
        <TooltipProvider>
          <Toaster />
          {loading ? (
            <PageLoader onComplete={() => setLoading(false)} />
          ) : (
            <div className="min-h-screen bg-background">
              <Navbar />
              <Router />
            </div>
          )}
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
