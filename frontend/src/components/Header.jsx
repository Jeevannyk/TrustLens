import Icon from "./Icon.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

export default function Header({ languages, language, onLanguageChange, theme, onToggleTheme, onOpenHistory, historyActive }) {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <div className="brand">
          <span className="brand-mark"><Icon name="shield-check" size={20} /></span>
          <span className="brand-name">TrustLens</span>
        </div>
        <div className="header-controls">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            aria-current={historyActive ? "page" : undefined}
            onClick={onOpenHistory}
          >
            <Icon name="clock" size={16} /> History
          </button>
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
