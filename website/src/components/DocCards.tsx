import React from 'react';
import Link from '@docusaurus/Link';

export type DocCard = {
  title: string;
  to: string;
  body: string;
};

/** A grid of linked cards for overview pages in the docs. */
export default function DocCards({ cards }: { cards: DocCard[] }): JSX.Element {
  return (
    <div className="doc-cards">
      {cards.map((card) => (
        <Link key={card.to} to={card.to} className="doc-card">
          <span className="doc-card__title">{card.title}</span>
          <span className="doc-card__body">{card.body}</span>
        </Link>
      ))}
    </div>
  );
}
