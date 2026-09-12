import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter } from "next/font/google";

import "@/styles/globals.css";

// next/font downloads Inter at build time and self-hosts it, so there is no
// request to Google at runtime. `variable` exposes it as a CSS custom property
// that src/styles/globals.css picks up as --font-sans.
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: {
    default: "WarrantyTrack",
    template: "%s · WarrantyTrack",
  },
  description:
    "Register products, upload receipts, and track warranty expiration in one place.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
