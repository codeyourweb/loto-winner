import { NumberBall } from "./NumberBall";

interface LotoGridProps {
  selected: number[];
  onToggle: (value: number) => void;
  disabled?: boolean;
  pickCount: number;
}

/** LOTO-style grid 1 → 49 (5 numbers to pick). */
export function LotoGrid({ selected, onToggle, disabled, pickCount }: LotoGridProps) {
  const isFull = selected.length >= pickCount;

  return (
    <div className="loto-grid" role="group" aria-label="Choix des 5 numéros">
      {Array.from({ length: 49 }, (_, index) => index + 1).map((value) => {
        const isSelected = selected.includes(value);
        const isBlocked = disabled || (!isSelected && isFull);
        return (
          <button
            key={value}
            type="button"
            className={`grid-cell${isSelected ? " is-selected" : ""}`}
            onClick={() => onToggle(value)}
            disabled={isBlocked}
            aria-pressed={isSelected}
            aria-label={`Numéro ${value}`}
          >
            {value}
          </button>
        );
      })}
    </div>
  );
}

interface ChancePickerProps {
  value: number | null;
  onChange: (value: number) => void;
  disabled?: boolean;
  chanceMax: number;
}

/** Lucky-number selector (1 → 10). */
export function ChancePicker({ value, onChange, disabled, chanceMax }: ChancePickerProps) {
  return (
    <div className="chance-picker">
      <p className="field-label">Numéro chance</p>
      <div className="chance-row" role="group" aria-label="Choix du numéro chance">
        {Array.from({ length: chanceMax }, (_, index) => index + 1).map((number) => (
          <button
            key={number}
            type="button"
            className={`chance-cell${value === number ? " is-selected" : ""}`}
            onClick={() => onChange(number)}
            disabled={disabled}
            aria-pressed={value === number}
            aria-label={`Numéro chance ${number}`}
          >
            <NumberBall value={number} variant="chance" size="sm" />
          </button>
        ))}
      </div>
    </div>
  );
}

interface SelectionPreviewProps {
  numbers: number[];
  chance: number | null;
  onClear: () => void;
  onRandom: () => void;
  disabled?: boolean;
}

/** Preview of the composed grid, with convenience actions. */
export function SelectionPreview({
  numbers,
  chance,
  onClear,
  onRandom,
  disabled,
}: SelectionPreviewProps) {
  return (
    <div className="preview">
      <div className="preview-balls">
        {[0, 1, 2, 3, 4].map((index) => {
          const value = numbers[index];
          return value ? (
            <NumberBall key={index} value={value} />
          ) : (
            <span key={index} className="ball ball-empty">
              ?
            </span>
          );
        })}
        <span className="preview-plus">+</span>
        {chance ? (
          <NumberBall value={chance} variant="chance" />
        ) : (
          <span className="ball ball-empty ball-chance-empty">?</span>
        )}
      </div>
      <div className="preview-actions">
        <button type="button" className="btn btn-ghost" onClick={onRandom} disabled={disabled}>
          🎲 Flash aléatoire
        </button>
        <button type="button" className="btn btn-ghost" onClick={onClear} disabled={disabled}>
          ♻️ Effacer
        </button>
      </div>
    </div>
  );
}
