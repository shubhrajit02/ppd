"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { MotionConfig } from "motion/react";
import { motionTokens } from "@/lib/motion";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: {
    staleTime: 1500, retry: 1, refetchOnWindowFocus: true,
  } } }));
  return <QueryClientProvider client={client}><MotionConfig reducedMotion="user" transition={{ duration: motionTokens.duration.normal, ease: motionTokens.easing.standard }}>{children}</MotionConfig></QueryClientProvider>;
}
