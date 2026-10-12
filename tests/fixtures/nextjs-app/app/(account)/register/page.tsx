'use client';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { registerSchema } from '../../../lib/schemas';
import { Field } from '../../../components/Field';
import { CountryCombobox } from '../../../components/CountryCombobox';

export default function RegisterPage() {
  const { register, control, handleSubmit } = useForm({ resolver: zodResolver(registerSchema) });
  return (
    <form onSubmit={handleSubmit(async (data) => { await fetch('/api/register', { method: 'POST', body: JSON.stringify(data) }); })}>
      <h1>Register</h1>
      <Field name="username" label="Username" register={register} />
      <Field name="email" label="Email" type="email" register={register} />
      <CountryCombobox control={control} name="country" />
      <label><input type="checkbox" {...register('newsletter')} /> Email me product news</label>
      <button type="submit">Register</button>
    </form>
  );
}
