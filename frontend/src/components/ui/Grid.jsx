import React from "react";
import { motion } from "framer-motion";

// Motion container that staggers its Card children in.
export default function Grid({ children, className = "" }) {
  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: 0.05 } } }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
