import Icon from "./Icon.jsx";

export default function ThemeToggle({ theme, onToggle }) {
  const dark = theme === "dark";
  return (
    <button
      type="button"
      className="icon-btn theme-toggle"
      aria-pressed={dark}
      aria-label="Dark mode"
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={onToggle}
    >
      <span className="theme-icon theme-icon-sun"><Icon name="sun" /></span>
      <span className="theme-icon theme-icon-moon"><Icon name="moon" /></span>
    </button>
  );
}
