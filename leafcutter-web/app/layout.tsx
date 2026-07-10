import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Sidebar, MobileNav } from "@/components/shell/sidebar";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
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
