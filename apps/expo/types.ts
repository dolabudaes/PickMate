export type RouteName = 'products' | 'product' | 'compare' | 'picki' | 'saved';

export type Category = string;
export type DevicePlatform = 'android' | 'ios' | 'any';
export type FitType = 'in_ear' | 'semi_in_ear' | 'general';
export type StockStatus = 'in_stock' | 'low_stock' | 'out_of_stock' | 'unknown';
export type Sentiment = 'positive' | 'neutral' | 'negative' | 'mixed';
export type EvidenceStrength = 'weak' | 'medium' | 'strong';
export type PriceStatus = 'Near historical low' | 'Good recent price' | 'Typical price' | 'High price' | 'Insufficient price data';

export type Product = {
  id: string;
  brand: string;
  name: string;
  slug: string;
  category: Category;
  description: string;
  currentPrice: number;
  originalPrice: number;
  currency: string;
  stockStatus: StockStatus;
  sellerType: string;
  deliveryText: string;
  returnPolicy: string;
  warrantyText: string;
  rating: number;
  reviewCount: number;
  imageUrls: string[];
  lastUpdatedAt: string;
  dataUpdatedAt: string;
  attributes: ProductAttribute;
  priceHistory: PriceHistory[];
  reviews: Review[];
  discussions: Discussion[];
  questions: ProductQuestion[];
  videos: VideoEvidence[];
  positiveThemes: string[];
  negativeThemes: string[];
  bestFor: string[];
  notFor: string[];
  sourceFields?: ProductSourceFields;
  standardizedDimensions?: Record<string, StandardizedDimension>;
};

export type ProductSourceFields = {
  schema: 'pickmate_mvp' | 'ecomagentbench_product_db' | 'pickmate_subset' | 'unknown';
  productId: string;
  title: string;
  mainCategory: string;
  store: string;
  brand: string;
  price: number | null;
  averageRating: number | null;
  ratingNumber: number;
  features: string[];
  description: string[];
  details: Record<string, unknown>;
  rawAttributes?: Record<string, unknown>;
};

export type StandardizedDimension = {
  key: string;
  label: string;
  score: number;
  polarity: 'positive' | 'negative' | 'mixed' | 'unknown';
  sources: Array<'price' | 'title' | 'features' | 'description' | 'details' | 'rating' | 'review' | 'behavior' | 'profile'>;
  evidence: string[];
};

export type ProductAttribute = {
  fitType: FitType;
  inEarDepth: 'shallow' | 'medium' | 'deep';
  noiseCancellationScore: number;
  noiseCancellationDepth: number;
  comfortScore: number;
  smallEarFriendly: boolean;
  singleEarWeight: number;
  earTipSizes: string[];
  callScore: number;
  windNoiseScore: number;
  batteryHours: number;
  totalBatteryHours: number;
  androidCompatible: boolean;
  iosCompatible: boolean;
  supportedCodecs: string[];
  multipoint: boolean;
  waterResistance: string;
  wirelessCharging: boolean;
  transparencyMode: boolean;
  appSupport: string[];
  microphoneCount: number;
};

export type PriceHistory = {
  id: string;
  productId: string;
  date: string;
  price: number;
  promotionType: string;
  source: string;
  verifiedAt: string;
};

export type Review = {
  id: string;
  productId: string;
  sourceType: 'platform' | 'long_term' | 'community';
  sourceName: string;
  content: string;
  rating: number;
  verifiedPurchase: boolean;
  usageDuration: string;
  userProfile: string;
  topics: string[];
  sentiment: Sentiment;
  helpfulCount: number;
  createdAt: string;
};

export type Discussion = {
  id: string;
  productId: string;
  sourceType: 'qa' | 'community' | 'long_term';
  sourceName: string;
  content: string;
  topic: string;
  sentiment: Sentiment;
  userProfile: string;
  createdAt: string;
};

export type ProductQuestion = {
  id: string;
  productId: string;
  question: string;
  answer: string;
  topic: string;
  sentiment: Sentiment;
};

export type VideoEvidence = {
  id: string;
  productId: string;
  videoTitle: string;
  creator: string;
  videoType: 'commute' | 'long_term' | 'call' | 'fit' | 'durability';
  sourceUrl: string;
  timestamp: string;
  findingType: 'physical_defect' | 'design_issue' | 'fit_issue' | 'interaction_issue' | 'wear_issue' | 'durability_risk' | 'call_quality_issue';
  finding: string;
  impactType: 'appearance_only' | 'minor_interaction' | 'scenario_dependent' | 'core_function' | 'uncertain';
  confirmedByCount: number;
  evidenceStrength: EvidenceStrength;
  createdAt: string;
};

export type UserIntent = {
  category: Category;
  budget: { min: number | null; max: number | null };
  hardConstraints: {
    inStock: boolean;
    devicePlatform: DevicePlatform;
    formFactor: FitType | null;
    brandOrStore?: string | null;
    requiredTerms?: string[];
    requiredAttributes?: Array<{ field: string; value: string; source: 'query' | 'profile' | 'clarification' }>;
  };
  useCases: string[];
  softPreferences: {
    noiseCancellation: number;
    comfort: number;
    callQuality: number;
    battery: number;
    priceValue: number;
    codecCompatibility: number;
    waterResistance: number;
    multipoint: number;
    quality: number;
    durability: number;
    reviewConfidence: number;
  };
  fitNeeds: {
    smallEarFriendly: boolean;
    avoidDeepInsertion: boolean;
  };
  dealbreakers: string[];
  explicitConcerns: string[];
  missingCriticalInformation: string[];
  productQuery: string;
  reviewEvidenceNeeds: string[];
  decisionDimensions: string[];
  rawText: string;
};

export type InferredPreference = {
  key: string;
  value: unknown;
  confidence: number;
  evidence: string[];
  status: 'inferred' | 'confirmed' | 'rejected';
};

export type SessionDecisionProfile = {
  budget?: { min?: number; max?: number };
  useCases: string[];
  devicePlatform?: DevicePlatform;
  priorities: Record<string, number>;
  explicitConcerns: string[];
  dealbreakers: string[];
  acceptedTradeoffs: string[];
  viewedProductIds?: string[];
  comparedProductIds?: string[];
  savedProductIds?: string[];
  chosenProductIds?: string[];
  rejectedProductIds?: string[];
};

export type LongTermDecisionProfile = {
  usualBudgetRange?: { min?: number; max?: number };
  devicePreferences: DevicePlatform[];
  stablePriorities: Record<string, number>;
  budgetPreference?: 'strict' | 'flexible' | 'quality_first' | 'unknown';
  priceSensitivity?: number;
  reliabilityPreference?: number;
  riskTolerance?: number;
  willingnessToPay?: Record<string, number>;
  confirmedTradeoffs: string[];
  shoppingStyle?: string[];
};

export type ShoppingDecisionProfile = {
  session: SessionDecisionProfile;
  longTerm: LongTermDecisionProfile;
  inferredPreferences: InferredPreference[];
  lastUpdatedAt: string;
};

export type BrowsingContext = {
  viewedProductIds: string[];
  comparedProductIds: string[];
  openedEvidenceTypes: string[];
  signals: Array<{ key: string; source: 'browsing'; label: string }>;
};

export type DecisionContext = {
  currentIntent: UserIntent;
  browsingContext: BrowsingContext;
  sessionProfile: SessionDecisionProfile;
  confirmedLongTermProfile: LongTermDecisionProfile;
  relevantInferredPreferences: InferredPreference[];
  profileSnapshot: ShoppingDecisionProfile;
};

export type ProfileSignal = {
  key: string;
  source: 'current_intent' | 'session' | 'confirmed' | 'inferred' | 'default';
  label: string;
};

export type RecommendationTrace = {
  profileSnapshot?: ShoppingDecisionProfile;
  profileSignalsUsed: ProfileSignal[];
  inferredPreferencesUsed: InferredPreference[];
  confirmedPreferencesUsed: ProfileSignal[];
  profileChangedRanking: boolean;
};

export type BrowsingEventName =
  | 'product_list_viewed'
  | 'product_viewed'
  | 'product_image_changed'
  | 'product_detail_section_opened'
  | 'price_history_opened'
  | 'reviews_opened'
  | 'negative_reviews_opened'
  | 'product_qa_opened'
  | 'video_evidence_opened'
  | 'product_added_to_compare'
  | 'product_removed_from_compare'
  | 'product_returned'
  | 'product_switched'
  | 'add_to_cart_clicked'
  | 'purchase_button_clicked'
  | 'picki_opened'
  | 'picki_dismissed'
  | 'picki_impression'
  | 'picki_open'
  | 'picki_dismiss'
  | 'decision_generated'
  | 'primary_recommendation_viewed'
  | 'alternative_viewed'
  | 'evidence_opened'
  | 'preference_updated'
  | 'recommendation_changed'
  | 'return_to_product'
  | 'add_to_cart_after_picki'
  | 'purchase_intent_after_picki';

export type BrowsingEvent = {
  id: string;
  name: BrowsingEventName;
  productId?: string;
  createdAt: string;
};

export type PriceAnalysis = {
  status: PriceStatus;
  average30: number | null;
  average90: number | null;
  low90: number | null;
  high90: number | null;
  deltaFrom90Average: number | null;
  deltaFrom90Low: number | null;
  explanation: string;
};

export type RecommendationEvidence = {
  type: 'attribute' | 'price' | 'review' | 'discussion' | 'video' | 'details' | 'profile' | 'conflict' | 'insufficient';
  title: string;
  detail: string;
  source: string;
  strength: EvidenceStrength;
};

export type RecommendationProduct = {
  product: Product;
  score: number;
  role: 'primary' | 'budget' | 'specialist';
  reasons: string[];
  cautions: string[];
  regretGuard: string;
  priceAnalysis: PriceAnalysis;
  evidence: RecommendationEvidence[];
  relevantRisks: RecommendationEvidence[];
};

export type RecommendationResult = {
  id: string;
  parsedIntent: UserIntent;
  excludedProducts: Array<{ product: Product; reason: string }>;
  primaryRecommendation: RecommendationProduct | null;
  alternatives: RecommendationProduct[];
  regretGuard: string;
  evidenceSummary: string;
  switchConditions?: Array<{
    condition: string;
    newPrimary: Product;
    reason: string;
  }>;
  fallbackUsed?: boolean;
  traceId?: string;
  missingInformation: string[];
  dataUpdatedAt: string;
  usedPreferences?: string[];
  trace: RecommendationTrace;
};

export type SavedDecision = {
  id: string;
  createdAt: string;
  userNeed: string;
  result: RecommendationResult;
};
