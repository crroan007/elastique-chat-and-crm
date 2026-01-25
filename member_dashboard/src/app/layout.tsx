import type { Metadata } from "next";
import { Playfair_Display, Inter } from "next/font/google";
import "./globals.css";

const playfair = Playfair_Display({
    subsets: ["latin"],
    variable: "--font-playfair",
    display: "swap",
});

const inter = Inter({
    subsets: ["latin"],
    variable: "--font-inter",
    display: "swap",
});

export const metadata: Metadata = {
    title: "Elastique CRM | Admin Dashboard",
    description: "Manage contacts, view timelines, and run marketing campaigns.",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en" className={`${playfair.variable} ${inter.variable}`} suppressHydrationWarning>
            <body className="font-sans bg-[#FDFDFD] text-[#2C3E50] antialiased">
                {children}
            </body>
        </html>
    );
}
