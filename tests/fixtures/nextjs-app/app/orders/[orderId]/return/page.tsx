'use client';
import { useFieldArray, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { returnSchema } from '../../../../lib/schemas';

export default function ReturnPage({ params }: { params: { orderId: string } }) {
  const { register, control, handleSubmit } = useForm({ resolver: zodResolver(returnSchema), defaultValues: { items: [{ sku: '', quantity: 1 }] } });
  const { fields, append } = useFieldArray({ control, name: 'items' });
  return (
    <form onSubmit={handleSubmit(async (data) => { await fetch(`/api/orders/${params.orderId}/returns`, { method: 'POST', body: JSON.stringify(data) }); })}>
      <h1>Return items</h1>
      <fieldset>
        <legend>Reason</legend>
        {['Damaged', 'Wrong item', 'No longer needed'].map((r) => <label key={r}><input type="radio" value={r} {...register('reason')} /> {r}</label>)}
      </fieldset>
      {fields.map((row, index) => (
        <div className="item-row" key={row.id}>
          <input aria-label="SKU" {...register(`items.${index}.sku`)} data-field="sku" />
          <input aria-label="Quantity" type="number" min={1} {...register(`items.${index}.quantity`)} data-field="quantity" />
        </div>
      ))}
      <button type="button" onClick={() => append({ sku: '', quantity: 1 })}>Add item</button>
      <label>Refund to
        <select {...register('refund_method')}><option>Original payment</option><option>Store credit</option></select>
      </label>
      <button type="submit">Request return</button>
    </form>
  );
}
