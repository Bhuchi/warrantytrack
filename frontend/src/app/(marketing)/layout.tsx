import type { ReactNode } from "react";

import Footer from "@/components/Footer";
import Header from "@/components/Header";

/**
 * Wraps every page in the (marketing) route group with the public site chrome.
 * The folder name is in parentheses, so it groups files without adding a URL
 * segment — the landing page stays at "/", not "/marketing".
 */
export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <Header />
      {children}
      <Footer />
    </>
  );
}
