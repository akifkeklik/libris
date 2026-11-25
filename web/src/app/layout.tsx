import type { Metadata } from "next";
import "./globals.css";
import "./themes.css";
import { cookies } from "next/headers";
import { translate } from "@/lib/i18n";
import { resolveLanguage } from "@/lib/preferences";
import { DEFAULT_THEME, LEGACY_THEME_MAP, THEME_IDS } from "@/lib/themes";
import { AuthProvider } from "@/components/AuthProvider";
import { PreferencesProvider } from "@/components/PreferencesProvider";
import { Navbar } from "@/components/Navbar";
import { SpotlightSearch } from "@/components/SpotlightSearch";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://libris-pink.vercel.app"),
  title: { default: "Libris | Remember what you read", template: "%s | Libris" },
  description: "Save a takeaway while you read. Libris turns it into a question and asks you again right before you would forget.",
  openGraph: {
    type: "website", siteName: "Libris", title: "Libris | Read it once. Remember it for good.",
    description: "Turn what you highlight into questions, and review them right before you would forget.",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Libris home page: Read it once. Remember it for good." }],
  },
  twitter: { card: "summary_large_image" },
  manifest: "/manifest.json",
  icons: { icon: [{ url: "/favicon.ico" }, { url: "/icon-192.png", type: "image/png", sizes: "192x192" }], apple: "/apple-touch-icon.png" },
  appleWebApp: { capable: true, title: "Libris", statusBarStyle: "black-translucent" },
};

const themeInitScript = `
(function() {
  try {
    var raw = localStorage.getItem('libris_user_preferences');
    var theme = 'dark';
    var palette = '${DEFAULT_THEME}';
    var themes = ${JSON.stringify(THEME_IDS)};
    var legacy = ${JSON.stringify(LEGACY_THEME_MAP)};
    var font = 'serif';
    var scale = '1.0';
    var spacing = 'normal';
    var contrast = 'false';
    var motion = 'normal';
    var density = 'comfortable';
    var lang = 'en';

    if (raw) {
      var p = JSON.parse(raw);
      if (p.themeMode === 'light') theme = 'light';
      else if (p.themeMode === 'system') {
        theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
      if (themes.indexOf(p.colorPalette) !== -1) palette = p.colorPalette;
      else if (legacy.hasOwnProperty(p.colorPalette)) palette = legacy[p.colorPalette];
      if (p.fontFamily) font = p.fontFamily;
      if (p.fontScale) scale = String(p.fontScale);
      if (p.lineSpacing) spacing = p.lineSpacing;
      if (p.highContrast) contrast = 'true';
      if (p.reducedMotion) motion = 'reduced';
      if (p.density) density = p.density;
      if (p.language) lang = p.language;
    } else {
      theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    var doc = document.documentElement;
    doc.setAttribute('data-theme', theme);
    doc.setAttribute('data-palette', palette);
    doc.setAttribute('data-font', font);
    doc.setAttribute('data-scale', scale);
    doc.setAttribute('data-spacing', spacing);
    doc.setAttribute('data-contrast', contrast);
    doc.setAttribute('data-motion', motion);
    doc.setAttribute('data-density', density);
    doc.setAttribute('lang', lang);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
    document.documentElement.setAttribute('data-palette', '${DEFAULT_THEME}');
  }
})();
`;

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const lang = resolveLanguage((await cookies()).get("libris_lang")?.value);
  return (
    <html lang={lang} suppressHydrationWarning>
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#0f172a" />
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <a href="#main-content" className="skip-link">{translate(lang, "skip_content")}</a>
        <PreferencesProvider initialLanguage={lang}>
          <AuthProvider>
            <SpotlightSearch />
            <Navbar />
            <main id="main-content" className="main-content">
              {children}
            </main>
          </AuthProvider>
        </PreferencesProvider>
      </body>
    </html>
  );
}
