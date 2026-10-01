import Icon from "./Icon.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

export default function Header({ languages, language, onLanguageChange, theme, onToggleTheme }) {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <div className="brand">
          <span className="brand-mark"><Icon name="shield-check" size={20} /></span>
          <span className="brand-name">TrustLens</span>
        </div>
        <div className="header-controls">
          <label className="lang-select">
            <span className="sr-only">Language of the result</span>
            <select value={language} onChange={(e) => onLanguageChange(e.target.value)}>
              {languages.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>
    </header>
  );
}
