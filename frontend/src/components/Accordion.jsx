import { useId, useState } from "react";
import Icon from "./Icon.jsx";

// items: [{ id, title, content, defaultOpen?, meta? }]. Each item toggles independently.
export default function Accordion({ items, headingLevel = 3, className = "" }) {
  return (
    <div className={`accordion ${className}`.trim()}>
      {items.map((item, i) => (
        <AccordionItem key={item.id ?? i} item={item} headingLevel={headingLevel} index={i} />
      ))}
    </div>
  );
}

function AccordionItem({ item, headingLevel, index }) {
  const [open, setOpen] = useState(Boolean(item.defaultOpen));
  const baseId = useId();
  const Heading = `h${headingLevel}`;
  return (
    <div className={`acc-item${open ? " acc-open" : ""}`}>
      <Heading className="acc-heading">
        <button
          type="button"
          className="acc-trigger"
          aria-expanded={open}
          aria-controls={`${baseId}-panel`}
          id={`${baseId}-btn`}
          onClick={() => setOpen((v) => !v)}
        >
          <span className="acc-title">{item.title}</span>
          {item.meta}
          <Icon name="chevron-down" size={18} className="acc-chevron" />
        </button>
      </Heading>
      <div
        className="acc-panel"
        id={`${baseId}-panel`}
        role="region"
        aria-labelledby={`${baseId}-btn`}
      >
        <div className="acc-panel-inner">
          <div className="acc-content">{item.content}</div>
        </div>
      </div>
    </div>
  );
}
