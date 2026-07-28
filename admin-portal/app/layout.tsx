import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stock Advisory — Admin Portal",
  description: "Operational back-office: watchlist and holdings management.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
