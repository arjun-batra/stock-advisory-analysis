import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stock Advisory — Admin Portal",
  description: "Operational back-office: watchlist and holdings management.",
};

// INC-13 (NFR8): explicit device-width viewport so phone/tablet breakpoints
// (docs/design/admin-portal.md §16.10) are evaluated against the device's
// actual logical width, not a desktop-emulated default.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
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
