import { ref } from "vue";

const STORAGE_KEY = "app_theme"; // light | dark | system
const theme = ref(localStorage.getItem(STORAGE_KEY) || "system");
const media = window.matchMedia("(prefers-color-scheme: dark)");

const applyTheme = () => {
  const dark = theme.value === "dark" || (theme.value === "system" && media.matches);
  document.documentElement.classList.toggle("dark", dark);
};

media.addEventListener("change", applyTheme);
applyTheme();

export function useTheme() {
  const setTheme = (value) => {
    const next = ["light", "dark", "system"].includes(value) ? value : "system";
    theme.value = next;
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme();
  };
  return { theme, setTheme };
}
