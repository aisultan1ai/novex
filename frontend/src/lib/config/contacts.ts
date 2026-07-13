// Публичные контакты, отображаемые в шапке/футере/лендингах.
// Значения берутся из NEXT_PUBLIC_* переменных окружения (файл .env), с
// разумными дефолтами для локальной разработки. Дефолты — только заглушки;
// на проде все три переменных должны быть переопределены в .env.
//
// Как поменять в проде:
//   .env:
//     NEXT_PUBLIC_SUPPORT_EMAIL=hello@company.kz
//     NEXT_PUBLIC_SUPPORT_PHONE=+7 (727) 123-45-67
//     NEXT_PUBLIC_PARTNERS_EMAIL=partners@company.kz
//     NEXT_PUBLIC_OFFICE_ADDRESS=Алматы, Казахстан
//
// NEXT_PUBLIC_ префикс обязателен — без него Next.js не подставит значение
// в клиентский бандл. После правки .env нужен ребилд фронта.

export const CONTACTS = {
  supportEmail: process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "support@novex.kz",
  supportPhone: process.env.NEXT_PUBLIC_SUPPORT_PHONE || "+7 (727) 000-00-00",
  partnersEmail: process.env.NEXT_PUBLIC_PARTNERS_EMAIL || "partners@novex.kz",
  officeAddress: process.env.NEXT_PUBLIC_OFFICE_ADDRESS || "Алматы, Казахстан",
} as const;

// Телефон для href="tel:" — убираем всё кроме цифр и ведущего +.
export function phoneHref(phone: string): string {
  const cleaned = phone.replace(/[^\d+]/g, "");
  return `tel:${cleaned}`;
}
