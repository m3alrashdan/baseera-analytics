import { notFound } from "next/navigation";
import { ProductRoute } from "@/components/product-route";
import { isLocale } from "@/lib/i18n";

export default async function LocaleRoute({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; slug?: string[] }>;
  searchParams: Promise<{ workspace?: string }>;
}) {
  const { locale, slug } = await params;
  const { workspace } = await searchParams;
  if (!isLocale(locale)) notFound();
  return (
    <ProductRoute
      locale={locale}
      route={(slug ?? ["analyst"]).join("/")}
      workspace={workspace}
    />
  );
}
