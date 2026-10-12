type Props = { name: string; label: string; options: string[]; required?: boolean };

export function SelectField({ name, label, options, required }: Props) {
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      <select id={name} name={name} required={required}>
        <option value="">Choose…</option>
        {options.map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    </div>
  );
}
