import type { Metadata } from "next";
import "@fontsource-variable/inter";
import "@fontsource-variable/geist-mono";
import "../components/redesign/design-system.css";

export const metadata: Metadata = {
  title: "+EV — Strategy verification workspace",
  description: "See which strategies have earned a keep, restrict or kill conversation, with the evidence attached.",
  applicationName: "+EV",
  icons: {
    icon: "/brand/plus-ev-mark.svg",
    shortcut: "/brand/plus-ev-mark.svg",
    apple: "/brand/plus-ev-mark.svg",
  },
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body className="kk-body">{children}</body></html>;
}
