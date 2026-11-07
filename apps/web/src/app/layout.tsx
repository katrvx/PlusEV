import type { Metadata } from "next";
import "@fontsource-variable/inter";
import "./globals.css";

export const metadata: Metadata = {
  title: "Keep or Kill — Strategy research workspace",
  description: "Investigate where your strategies work. Inspect agent research, challenge hypotheses, and review the evidence.",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
