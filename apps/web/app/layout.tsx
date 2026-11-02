import "./globals.css";
import { Shell } from "@/components/shell";
export const metadata = { title: "VaultLine Verify", description: "Financial evidence verification workspace" };
export default function Layout({children}: {children: React.ReactNode}) { return <html lang="en"><body><a href="#main" className="sr-only focus:not-sr-only">Skip to content</a><Shell>{children}</Shell></body></html>; }
