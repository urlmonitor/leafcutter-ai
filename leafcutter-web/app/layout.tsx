import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar, MobileNav } from "@/components/shell/sidebar";

// IBM Plex Sans — humanist, highly legible on dark UI. Kept under the existing
// --font-geist-* variable names so the Tailwind theme + all refs work unchanged.
const geistSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-geist-sans",
  display: "swap",
});
const geistMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-geist-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Leafcutter Atlas — project intelligence",
  description:
    "A living map of the Leafcutter project: acceptance criteria, roadmap, build pipeline, and architecture — read live from the repo.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <div className="flex min-h-svh">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <MobileNav />
            <main className="mx-auto w-full max-w-[1400px] flex-1 px-5 py-8 sm:px-8">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
