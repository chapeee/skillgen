import { z } from 'zod';

export const contactSchema = z.object({
  name: z.string().min(2).max(60),
  email: z.string().email(),
  topic: z.enum(['Sales', 'Support', 'Billing', 'Other']),
  order_number: z.string().regex(/^ORD-[0-9]{6}$/).optional(),
  message: z.string().min(20).max(2000),
});

export const registerSchema = z.object({
  username: z.string().regex(/^[a-z][a-z0-9-]{2,23}$/),
  email: z.string().email(),
  country: z.string(),
  newsletter: z.boolean().default(false),
});

export const returnSchema = z.object({
  reason: z.enum(['Damaged', 'Wrong item', 'No longer needed']),
  items: z.array(z.object({ sku: z.string(), quantity: z.number().int().min(1) })).min(1),
  refund_method: z.enum(['Original payment', 'Store credit']),
});
