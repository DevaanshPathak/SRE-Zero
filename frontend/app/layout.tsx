import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SRE-Zero Console",
  description: "Interactive frontend for the SRE-Zero incident-response benchmark"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

