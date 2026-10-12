type Props = { name: string; label: string; type?: string; required?: boolean; maxLength?: number; help?: string };

export function TextField({ name, label, type = 'text', required, maxLength, help }: Props) {
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      <input id={name} name={name} type={type} required={required} maxLength={maxLength} data-testid={`field-${name}`} />
      {help && <p className="help">{help}</p>}
    </div>
  );
}
