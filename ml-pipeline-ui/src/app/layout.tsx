import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Neural Observatory | ML Pipeline",
  description: "Autonomous ML pipeline monitoring and control",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-neural-grid antialiased custom-scrollbar">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
