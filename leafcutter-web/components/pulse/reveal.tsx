"use client";

import * as React from "react";
import { motion } from "framer-motion";

/**
 * Subtle entrance motion for Pulse sections — a short fade + rise. Pass a
 * `delay` (seconds) to stagger a row of siblings. Children are server-rendered
 * and handed through untouched, so this stays a thin client boundary.
 */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
