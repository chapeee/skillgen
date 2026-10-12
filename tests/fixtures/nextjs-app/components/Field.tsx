import { UseFormRegister } from 'react-hook-form';

export function Field({ name, label, register, type = 'text' }: { name: string; label: string; register: UseFormRegister<any>; type?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type={type} {...register(name)} aria-label={label} />
    </label>
  );
}
