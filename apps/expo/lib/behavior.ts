import type { BrowsingEvent, BrowsingEventName } from '../types';

export function createEvent(name: BrowsingEventName, productId?: string): BrowsingEvent {
  return { id: `${name}-${Date.now()}-${Math.random().toString(16).slice(2)}`, name, productId, createdAt: new Date().toISOString() };
}

export function shouldTriggerPicki(events: BrowsingEvent[], dismissedAtCount = -99) {
  const afterDismiss = events.slice(Math.max(0, dismissedAtCount + 2));
  const viewed = new Set(events.filter((event) => event.name === 'product_viewed').map((event) => event.productId).filter(Boolean));
  const switched = events.filter((event) => event.name === 'product_switched').length;
  const priceAndNegative = events.some((event) => event.name === 'price_history_opened') && events.some((event) => event.name === 'negative_reviews_opened');
  const cartAbandoned = events.some((event) => event.name === 'add_to_cart_clicked') && !events.some((event) => event.name === 'purchase_button_clicked');
  if (dismissedAtCount >= 0 && afterDismiss.filter((event) => event.name === 'product_viewed').length < 2) return { trigger: false, reason: '' };
  if (viewed.size >= 3) return { trigger: true, reason: 'You just viewed at least three products, so Picki is ready to help.' };
  if (switched >= 2) return { trigger: true, reason: 'You switched between products several times, so Picki can help compare them.' };
  if (priceAndNegative) return { trigger: true, reason: 'You checked both price trends and negative reviews, so Picki can help verify the tradeoffs.' };
  if (cartAbandoned) return { trigger: true, reason: 'You paused before buying, so Picki can help double-check the choice.' };
  return { trigger: false, reason: '' };
}
