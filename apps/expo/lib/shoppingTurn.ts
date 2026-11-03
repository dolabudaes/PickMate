import type { Product } from '../types';

export type PickAction = 'message' | 'cheaper' | 'different_style' | 'compare' | 'why_this' | 'focus' | 'promote';

export type LivePickCard = {
  product: Product;
  whyForYou: string;
  oneCaution: string;
  referencePrice: number | null;
  priceLabel: string | null;
  amazonUrl: string | null;
  priceVerifiedAt: string | null;
};

export type ShoppingMemory = {
  id: string;
  facet: string;
  value: string;
  label: string;
  scope: string;
  source: string;
  evidence?: string | null;
  enabled: boolean;
  sourceType?: 'explicit' | 'inferred';
  status?: 'active' | 'suggested' | 'dismissed' | 'superseded';
  userConfirmed?: boolean;
  normalizedPreference?: string;
  originalUserExpression?: string | null;
  supportingEvidenceCount?: number;
  evidenceSnippets?: string[];
  conversationIds?: string[];
  priority?: number;
};

export type ComparisonReason = {
  title: string;
  body: string;
};

export type ComparisonDiff = {
  label: string;
  values: string[];
};

export type ComparisonExplanation = {
  winnerProductId?: string | null;
  headline: string;
  summary: string;
  verdict?: string;
  reasons: ComparisonReason[];
  diffs: ComparisonDiff[];
  preferenceNote?: string | null;
  limitation?: string | null;
};

export type CartItem = {
  id: string;
  productId: string;
  conversationId: string | null;
  sourceType: string;
  title: string;
  price: number | null;
  createdAt: string;
  product?: Product;
};

export type SavedPick = {
  id: string;
  productId: string;
  conversationId: string | null;
  reason: string;
  title: string;
  price: number | null;
  createdAt: string;
  product?: Product;
};

export type MemoryEvent = { id: string; label: string } | null;

export type TasteSavedEvent = {
  id: string;
  ids: string[];
  labels: string[];
  label: string;
  undoable: boolean;
  sourceType?: 'explicit' | 'inferred';
} | null;

export type ComparisonSnapshot = {
  productId: string;
  title: string;
  brand: string;
  kind: string;
  referencePrice: number | null;
  rating: number | null;
  reviewCount: number;
  feature: string | null;
  caution: string | null;
};

export type ComparisonRecord = {
  id: string;
  title: string;
  verdict: string;
  winnerProductId: string | null;
  conversationId: string | null;
  createdAt: string;
  products: ComparisonSnapshot[];
  explanation?: ComparisonExplanation | null;
};

export type RelatedChat = {
  id: string;
  title: string;
  updatedAt: string;
  relatedProductCount?: number;
};

export type ProposedShoppingAction = {
  id: string;
  type: 'cart_update' | 'preference_update';
  summary: string;
  payload: Record<string, unknown>;
  status: 'proposed' | 'validated' | 'confirmed' | 'executed' | 'failed';
};

export type SuggestedPickiAction = {
  id: string;
  label: string;
  kind: 'quick' | 'message';
  action?: 'cheaper' | 'compare' | 'why_this';
  message?: string;
  href?: string;
};

export type PickiClarificationOption = {
  id: string;
  label: string;
  message: string;
};

export type PickiComparisonData = {
  winnerProductId?: string | null;
  columns?: Array<{ productId?: string; title?: string; price?: number | null }>;
  rows?: Array<{ label: string; values: string[] }>;
  summary?: string;
};

export type PickiDetailSection = {
  id: string;
  title: string;
  collapsed: boolean;
  lines: string[];
};

export type PickiProductRef = {
  productId?: string;
  role?: string;
  badge?: string;
  title?: string;
  brand?: string;
  price?: number | null;
  specLine?: string | null;
};

export type StructuredPickiResponse = {
  message: string;
  responseMode?: 'QUICK' | 'STANDARD' | 'DEEP' | null;
  primaryMessage?: string | null;
  keyFacts?: Array<{ text: string }>;
  productRefs?: PickiProductRef[];
  detailSections?: PickiDetailSection[];
  suggestedActions?: SuggestedPickiAction[];
  directRecommendation?: string | null;
  productHighlights?: string[];
  technicalSpecifications?: string[];
  priceValueAnalysis?: string | null;
  customerReviewSummary?: string | null;
  productComparisons?: string | null;
  importantDrawbacks?: string[];
  suggestedFollowUpQuestions?: string[];
  proposedActions?: ProposedShoppingAction[];
  evidenceNotes?: string[];
  responseType?: string | null;
  comparisonData?: PickiComparisonData | null;
  clarificationOptions?: PickiClarificationOption[];
  decisionHighlight?: string | null;
  evidenceStatus?: string | null;
  decisionBrief?: {
    angles?: Array<{ id: string; title: string; body: string }>;
    review?: { available: boolean; lines: string[]; quotes: Array<{ productId?: string; snippet?: string }> } | null;
    gap?: string | null;
    changeCondition?: string | null;
    switches?: Array<{ id: string; label: string; message: string }>;
    evidence?: Array<{
      source?: string;
      productId?: string;
      evidenceType?: string;
      claim?: string;
      availability?: string;
      decisionRelevance?: string;
    }>;
    winnerProductId?: string | null;
  } | null;
};

export type PickTurnResult = {
  conversationId: string;
  message: string;
  activePick: LivePickCard | null;
  alternatives: LivePickCard[];
  quickActions: Array<'cheaper' | 'different_style' | 'compare' | 'why_this'>;
  changedSinceLastPick: string[];
  memoryEvent: MemoryEvent;
  structuredResponse?: StructuredPickiResponse | null;
  proposedActions?: ProposedShoppingAction[];
  agentTraceId?: string | null;
  tasteSaved?: TasteSavedEvent;
};

export const QUICK_ACTION_LABELS: Record<'cheaper' | 'different_style' | 'compare' | 'why_this', string> = {
  cheaper: 'Find a cheaper option',
  different_style: 'Try a different option',
  compare: 'Compare products',
  why_this: 'Why this recommendation?',
};
