import { Laptop, Moon, Sun } from "lucide-react";

import { useTheme, type Theme } from "@/app/providers/theme-provider";

const themeSequence: Theme[] = ["system", "light", "dark"];
const labels: Record<Theme, string> = {
  system: "Tema del sistema",
  light: "Tema claro",
  dark: "Tema oscuro",
};

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const currentIndex = themeSequence.indexOf(theme);
  const nextTheme =
    themeSequence[(currentIndex + 1) % themeSequence.length] ?? "system";
  const Icon = theme === "system" ? Laptop : theme === "light" ? Sun : Moon;

  return (
    <button
      aria-label={`${labels[theme]}. Cambiar a ${labels[nextTheme].toLocaleLowerCase("es")}.`}
      className="icon-button"
      onClick={() => setTheme(nextTheme)}
      title={labels[theme]}
      type="button"
    >
      <Icon aria-hidden="true" className="size-4.5" />
    </button>
  );
}
