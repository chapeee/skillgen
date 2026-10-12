'use client';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { contactSchema } from '../../lib/schemas';
import { Field } from '../../components/Field';

export default function ContactPage() {
  const { register, watch, handleSubmit } = useForm({ resolver: zodResolver(contactSchema) });
  const topic = watch('topic');
  const onSubmit = handleSubmit(async (data) => {
    await fetch('/api/contact', { method: 'POST', body: JSON.stringify(data) });
    window.location.assign('/contact/thanks');
  });
  return (
    <form onSubmit={onSubmit}>
      <h1>Contact us</h1>
      <Field name="name" label="Your name" register={register} />
      <Field name="email" label="Email" type="email" register={register} />
      <label>Topic
        <select {...register('topic')}>
          {['Sales', 'Support', 'Billing', 'Other'].map((t) => <option key={t}>{t}</option>)}
        </select>
      </label>
      {topic === 'Billing' && <Field name="order_number" label="Order number" register={register} />}
      <label>Message <textarea {...register('message')} rows={6} /></label>
      <button type="submit">Send message</button>
    </form>
  );
}
