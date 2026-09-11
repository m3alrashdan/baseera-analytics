"use client";

import { useEffect } from "react";
import type { Locale } from "@/lib/contracts";
import { directionFor } from "@/lib/i18n";

export function LocaleDocument({ locale }: { locale: Locale }) {
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = directionFor(locale);
    document.body.dir = directionFor(locale);
  }, [locale]);
  return null;
}
