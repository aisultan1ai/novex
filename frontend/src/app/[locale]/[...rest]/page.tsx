import { notFound } from "next/navigation";

// Любой несуществующий путь внутри локали отдаёт локализованную 404.
export default function CatchAll() {
  notFound();
}
