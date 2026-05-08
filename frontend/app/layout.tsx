import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Providers from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Docstribe OPD Dashboard",
  description: "LLM-powered OPD Clinical Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-[var(--color-background)] text-[var(--color-text-main)] antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
