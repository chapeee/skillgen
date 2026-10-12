import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextField } from '../components/TextField';
import { SelectField } from '../components/SelectField';
import { post } from '../api/client';

const PLANS = ['Starter', 'Team', 'Enterprise'];

export default function Signup() {
  const navigate = useNavigate();
  const [plan, setPlan] = useState('');
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    await post('/signup', data);
    navigate('/welcome');
  }
  return (
    <form onSubmit={submit}>
      <h1>Create your account</h1>
      <TextField name="full_name" label="Full name" required maxLength={80} />
      <TextField name="work_email" label="Work email" type="email" required />
      <TextField name="password" label="Password" type="password" required help="At least 12 characters." />
      <SelectField name="plan" label="Plan" options={PLANS} required />
      {plan === 'Enterprise' && <TextField name="seats" label="Number of seats" type="number" required />}
      <label><input type="checkbox" name="accept_terms" required /> I accept the terms</label>
      <button type="submit">Create account</button>
    </form>
  );
}
