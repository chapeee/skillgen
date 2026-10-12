'use client';
import { useState } from 'react';
import { Control, useController } from 'react-hook-form';

export function CountryCombobox({ control, name }: { control: Control<any>; name: string }) {
  const { field } = useController({ control, name });
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState<string[]>([]);
  async function search(text: string) {
    setQuery(text);
    const response = await fetch(`/api/countries?q=${encodeURIComponent(text)}`);
    setOptions(await response.json());
  }
  return (
    <div>
      <label id="country-label">Country</label>
      <input role="combobox" aria-labelledby="country-label" aria-controls="country-list" aria-expanded={options.length > 0}
             value={query} onChange={(e) => search(e.target.value)} />
      <ul id="country-list" role="listbox">
        {options.map((option) => <li role="option" key={option} onClick={() => { field.onChange(option); setQuery(option); setOptions([]); }}>{option}</li>)}
      </ul>
    </div>
  );
}
