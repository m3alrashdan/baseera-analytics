import "@fontsource-variable/manrope";
import "@fontsource-variable/noto-sans-arabic";
import "./globals.css";

export const metadata = {
  title: { default: "BASEERA | بصيرة", template: "%s · BASEERA" },
  description: "Evidence-led enterprise analytics and decision support.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
