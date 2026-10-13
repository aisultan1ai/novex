import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";

// Локализованные обёртки над next/link и next/navigation: сохраняют префикс
// /kz при переходах. Используйте их вместо импортов из "next/link" и
// useRouter/usePathname/redirect из "next/navigation".
export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
