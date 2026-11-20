import type { Metadata } from "next";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "./globals.css";
import "./polish.css";
import { Providers } from "@/components/providers";
import { Agentation } from "agentation"

export const metadata: Metadata = { title: "AICR — Code intelligence, grounded", description: "Review code with evidence, explainable scores and a shared analysis engine." };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en">
    <body>
    <Providers>{children}
       {process.env.NODE_ENV === "development" && <Agentation />}
    </Providers>
    </body>
  </html>;
}
