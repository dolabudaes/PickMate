import type { Discussion, PriceHistory, Product, ProductQuestion, RecommendationEvidence, RecommendationProduct, RecommendationResult, Review, VideoEvidence } from '../types';

const phraseMap: Array<[RegExp, string]> = [
  [/这次只比较你在清单中选中的商品。结合已有购物条件，(.+?) 更符合当前需求；下面保留了最关键的差异，结论会在接口、最低性能或使用距离变化时重新评估。/g, 'This comparison only includes the products you selected in My Picks. Based on your current requirements, $1 is the better fit. The key differences are shown below, and the conclusion may change if the connector, minimum performance, or required cable length changes.'],
  [/这次只比较你在清单中选中的商品。/g, 'This comparison only includes the products you selected in My Picks.'],
  [/^视频能力$/g, 'Video capability'],
  [/^接口$/g, 'Connectors'],
  [/^使用距离$/g, 'Required length'],
  [/^依据与限制$/g, 'Evidence and limitations'],
  [/^更换对比商品$/g, 'Change comparison products'],
  [/^查看评价依据$/g, 'View review evidence'],
  [/当前有货/g, 'In stock'],
  [/少量有货/g, 'Low stock'],
  [/tws_anc_earbuds/g, 'ANC earbuds'],
  [/platform_coupon/g, 'Platform coupon'],
  [/daily_price/g, 'Daily price'],
  [/品牌旗舰店/g, 'Brand flagship store'],
  [/次日达/g, 'Next-day delivery'],
  [/7 天无理由/g, '7-day no-reason returns'],
  [/官方一年保修/g, 'Official one-year warranty'],
  [/MVP 样例价格历史/g, 'MVP sample price history'],
  [/MVP 商品库/g, 'MVP product catalog'],
  [/MVP 样例数据/g, 'MVP sample data'],
  [/真无线主动降噪耳机/g, 'true wireless ANC earbuds'],
  [/主动降噪评分\s*(\d+)/g, 'Active noise cancellation score $1'],
  [/舒适度评分\s*(\d+)/g, 'Comfort score $1'],
  [/通话评分\s*(\d+)/g, 'Call score $1'],
  [/不支持 LDAC 或 LHDC/g, 'Does not support LDAC or LHDC'],
  [/支持\s*([^，。,]+)\s*高清编码/g, 'Supports $1 hi-res codec'],
  [/支持\s*([^，。,]+)\s*编码/g, 'Supports $1 codec'],
  [/支持\s*([^，。,]+)/g, 'Supports $1'],
  [/^Android 编码$/g, 'Android codec'],
  [/^耳塞尺寸$/g, 'Ear tip sizes'],
  [/^降噪参数$/g, 'ANC specs'],
  [/^评价数据$/g, 'Review data'],
  [/^单耳重量$/g, 'Single-ear weight'],
  [/^通话评分$/g, 'Call score'],
  [/^降噪评分$/g, 'ANC score'],
  [/^价格$/g, 'Price'],
  [/^库存$/g, 'Stock'],
  [/^续航$/g, 'Battery life'],
  [/自适应主动降噪/g, 'Adaptive active noise cancellation'],
  [/多尺寸耳塞/g, 'Multiple ear tip sizes'],
  [/价格低于近期均价/g, 'Price is below the recent average'],
  [/不是三款里最轻/g, 'Not the lightest in the compared set'],
  [/触控操作偶尔容易误触/g, 'Touch controls can misfire occasionally'],
  [/触控容易误触/g, 'Touch controls can misfire occasionally'],
  [/通话表现不是最突出/g, 'Call quality is not the strongest point'],
  [/价格更低/g, 'Lower price'],
  [/价格很低/g, 'Very low price'],
  [/降噪和续航均衡/g, 'Balanced ANC and battery life'],
  [/评价数量较多/g, 'Large review sample'],
  [/续航够用/g, 'Battery life is enough'],
  [/降噪弱于 Liberty 4 NC/g, 'ANC is weaker than Liberty 4 NC'],
  [/耳塞腔体略大/g, 'Earbud body is slightly large'],
  [/小耳型适配一般/g, 'Small-ear fit is average'],
  [/小耳型适配不突出/g, 'Small-ear fit is not a standout'],
  [/小耳型适配更友好/g, 'More friendly for smaller ears'],
  [/长时间佩戴压力较小/g, 'Lower pressure during long wear'],
  [/单耳重量较轻/g, 'Lighter single-ear weight'],
  [/续航时间更长/g, 'Longer battery life'],
  [/价格接近预算上限/g, 'Price is close to the budget limit'],
  [/部分高级功能在 OPPO 手机上体验更完整/g, 'Some advanced features work best on OPPO phones'],
  [/降噪强度不是最高/g, 'ANC strength is not the highest'],
  [/Android 适配较好/g, 'Good Android fit'],
  [/综合体验均衡/g, 'Balanced overall experience'],
  [/重量控制不错/g, 'Good weight control'],
  [/降噪不如主推荐稳定/g, 'ANC is less stable than the top pick'],
  [/耳塞尺寸选择较少/g, 'Fewer ear tip size options'],
  [/支持 LDAC/g, 'Supports LDAC'],
  [/支持 LHDC/g, 'Supports LHDC'],
  [/续航较长/g, 'Longer battery life'],
  [/佩戴舒适度一般/g, 'Comfort is average'],
  [/通话表现较稳/g, 'Call quality is relatively stable'],
  [/通话表现中上/g, 'Call quality is above average'],
  [/降噪表现中上/g, 'ANC performance is above average'],
  [/降噪表现强/g, 'Strong ANC performance'],
  [/库存充足/g, 'Stock is available'],
  [/单次续航较短/g, 'Single-charge battery life is shorter'],
  [/重量略高/g, 'Slightly heavier'],
  [/重量较轻/g, 'Lighter weight'],
  [/入门门槛低/g, 'Low entry price'],
  [/降噪能力弱/g, 'ANC capability is weak'],
  [/单次续航短/g, 'Shorter single-charge battery life'],
  [/不适合作为地铁降噪优先选择/g, 'Not ideal if subway ANC is the top priority'],
  [/价格留有余量/g, 'Leaves room in the budget'],
  [/佩戴较轻/g, 'Lighter fit'],
  [/降噪能力不算强/g, 'ANC is not especially strong'],
  [/品牌生态功能较少/g, 'Fewer brand ecosystem features'],
  [/声音风格耐听/g, 'Easygoing sound tuning'],
  [/佩戴稳定/g, 'Stable fit'],
  [/明显超出 500 元预算/g, 'Clearly over a 500 budget'],
  [/超出 500 元预算/g, 'Over a 500 budget'],
  [/价格接近上限/g, 'Price is close to the limit'],
  [/价格高/g, 'High price'],
  [/Android 高清编码不突出/g, 'Android hi-res codec support is not a standout'],
  [/轻量舒适/g, 'Light and comfortable'],
  [/价格符合预算/g, 'Fits the budget'],
  [/系统弹窗体验较好/g, 'Better system pairing pop-up experience'],
  [/续航偏短/g, 'Battery life is on the shorter side'],
  [/外观辨识度高/g, 'Distinctive design'],
  [/设计感优先但价格不低/g, 'Design-forward, but not cheap'],
  [/降噪明显/g, 'Noticeable noise cancellation'],
  [/通勤安静很多/g, 'Commutes feel much quieter'],
  [/续航稳定/g, 'Steady battery life'],
  [/价格友好/g, 'Friendly price'],
  [/日常够用/g, 'Enough for everyday use'],
  [/连接稳定/g, 'Stable connection'],
  [/佩戴轻便/g, 'Lightweight fit'],
  [/性价比高/g, 'Good value'],
  [/佩戴偏胀/g, 'Fit can feel tight'],
  [/佩戴略胀/g, 'Fit can feel a little tight'],
  [/降噪不算很强/g, 'ANC is not especially strong'],
  [/佩戴轻/g, 'Light fit'],
  [/续航长/g, 'Long battery life'],
  [/日常体验稳定/g, 'Stable daily experience'],
  [/功能适配有品牌差异/g, 'Feature support varies by phone brand'],
  [/音质清晰/g, 'Clear sound'],
  [/连接快/g, 'Fast connection'],
  [/风噪控制一般/g, 'Wind-noise control is average'],
  [/音质不错/g, 'Good sound quality'],
  [/续航较稳/g, 'Battery life is stable'],
  [/腔体略大/g, 'Earbud body is slightly large'],
  [/通话清晰/g, 'Clear calls'],
  [/降噪够用/g, 'ANC is usable'],
  [/续航一般/g, 'Battery life is average'],
  [/佩戴略撑/g, 'Fit can feel a little tight'],
  [/便宜/g, 'Cheap'],
  [/外观轻巧/g, 'Lightweight design'],
  [/听歌够用/g, 'Enough for music listening'],
  [/降噪有限/g, 'Limited ANC'],
  [/App 功能普通/g, 'App features are basic'],
  [/声音好听/g, 'Pleasant sound'],
  [/做工不错/g, 'Good build quality'],
  [/价格偏高/g, 'Price is on the high side'],
  [/编码规格普通/g, 'Codec specs are basic'],
  [/佩戴舒服/g, 'Comfortable fit'],
  [/降噪稳定/g, 'Stable ANC'],
  [/体积小/g, 'Compact size'],
  [/通话清楚/g, 'Clear calls'],
  [/外观好看/g, 'Good-looking design'],
  [/降噪不是最强/g, 'ANC is not the strongest'],
  [/地铁通勤/g, 'Subway commuting'],
  [/办公专注/g, 'Office focus'],
  [/日常步行/g, 'Daily walking'],
  [/学生日常/g, 'Student daily use'],
  [/视频娱乐/g, 'Video entertainment'],
  [/长时间通勤/g, 'Long commutes'],
  [/日常通勤/g, 'Daily commuting'],
  [/游戏娱乐/g, 'Gaming and entertainment'],
  [/预算有限/g, 'Budget-limited shopping'],
  [/在线会议/g, 'Online meetings'],
  [/通勤降噪/g, 'Commute ANC'],
  [/降噪通勤/g, 'ANC commuting'],
  [/办公电话/g, 'Office calls'],
  [/华为设备/g, 'Huawei devices'],
  [/低预算入门/g, 'Low-budget entry'],
  [/日常听歌/g, 'Daily music listening'],
  [/视频会议/g, 'Video meetings'],
  [/轻办公/g, 'Light office work'],
  [/音乐听感/g, 'Music listening'],
  [/跨设备使用/g, 'Cross-device use'],
  [/轻量佩戴/g, 'Lightweight wearing'],
  [/长期办公/g, 'Long office use'],
  [/安卓通勤/g, 'Android commuting'],
  [/办公会议/g, 'Office meetings'],
  [/设计感穿搭/g, 'Design-forward outfits'],
  [/安卓听歌/g, 'Android music listening'],
  [/小耳型用户反馈整体中上/g, 'small-ear feedback is generally above average'],
  [/小耳型用户反馈存在分歧/g, 'small-ear feedback is mixed'],
  [/小耳型反馈存在分歧/g, 'Small-ear feedback is mixed'],
  [/通话一般/g, 'Average call quality'],
  [/通话表现一般/g, 'Average call quality'],
  [/降噪一般/g, 'ANC is average'],
  [/风噪明显/g, 'Noticeable wind noise'],
  [/小耳反馈分歧/g, 'Mixed small-ear feedback'],
  [/安卓手机/g, 'Android phone'],
  [/轻通勤/g, 'Light commuting'],
  [/通勤/g, 'Commuting'],
  [/Android 用户/g, 'Android users'],
  [/重视综合稳定/g, 'Balanced stability'],
  [/轻度降噪需求/g, 'Light ANC needs'],
  [/每天大量电话会议/g, 'Many daily phone meetings'],
  [/强通话优先用户/g, 'Call-quality-first shoppers'],
  [/对外观划痕极敏感的人/g, 'Shoppers highly sensitive to cosmetic scratches'],
  [/长期使用反馈/g, 'Long-term feedback'],
  [/平台评价/g, 'Platform review'],
  [/两周以上/g, 'More than two weeks'],
  [/三天内/g, 'Within three days'],
  [/Android 用户，小耳型/g, 'Android user, smaller ears'],
  [/通勤用户/g, 'Commuter'],
  [/小耳型佩戴/g, 'Small-ear fit'],
  [/电话会议/g, 'Phone meetings'],
  [/地铁降噪/g, 'Subway ANC'],
  [/售后保修/g, 'Warranty support'],
  [/长期讨论/g, 'Long-term discussion'],
  [/商品问答/g, 'Product Q&A'],
  [/反馈可参考，和商品参数基本一致/g, 'feedback is available and broadly matches the product specs'],
  [/通话表现够用但不是强项，高频会议建议谨慎/g, 'Calls are usable but not a strength, so heavy meeting use needs caution'],
  [/小耳朵戴着会不会胀？/g, 'Will they feel tight for smaller ears?'],
  [/多数小耳型用户反馈可以接受/g, 'Most smaller-ear feedback is acceptable'],
  [/建议谨慎/g, 'check carefully'],
  [/安卓手机音质怎么样？/g, 'How is sound quality on Android?'],
  [/Android 兼容可用/g, 'Android compatibility is usable'],
  [/电话会议清楚吗？/g, 'Are phone meetings clear?'],
  [/室内会议更稳定/g, 'more stable for indoor meetings'],
  [/通话不是强项，风噪环境清晰度会下降/g, 'Calls are not a strength, and wind can reduce voice clarity'],
  [/两周后外观情况/g, 'Appearance after two weeks'],
  [/长期佩戴体验/g, 'Long-wear fit test'],
  [/通话实测/g, 'Call quality test'],
  [/MVP 样例视频/g, 'MVP sample video'],
  [/充电盒容易出现细小划痕/g, 'Charging case can pick up fine scratches'],
  [/调整佩戴时可能误触/g, 'Adjusting the fit can trigger accidental touches'],
  [/户外风噪环境下通话清晰度下降/g, 'Outdoor wind can reduce call clarity'],
];

const brandMap: Record<string, string> = {
  小米: 'Xiaomi',
  漫步者: 'Edifier',
  HUAWEI: 'Huawei',
  HONOR: 'Honor',
  EDIFIER: 'Edifier',
};

export function humanizeText(value: string) {
  let text = brandMap[value] ?? value;
  for (const [pattern, replacement] of phraseMap) text = text.replace(pattern, replacement);
  return text
    .replace(/，/g, ', ')
    .replace(/。/g, '.')
    .replace(/、/g, ', ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function humanizeProduct(product: Product): Product {
  return {
    ...product,
    brand: humanizeText(product.brand),
    name: humanizeText(product.name),
    description: humanizeText(product.description),
    sellerType: humanizeText(product.sellerType),
    deliveryText: humanizeText(product.deliveryText),
    returnPolicy: humanizeText(product.returnPolicy),
    warrantyText: humanizeText(product.warrantyText),
    priceHistory: product.priceHistory.map(humanizePriceHistory),
    reviews: (product.reviews ?? []).map(humanizeReview),
    discussions: product.discussions.map(humanizeDiscussion),
    questions: product.questions.map(humanizeQuestion),
    videos: product.videos.map(humanizeVideo),
    positiveThemes: product.positiveThemes.map(humanizeText),
    negativeThemes: product.negativeThemes.map(humanizeText),
    bestFor: product.bestFor.map(humanizeText),
    notFor: product.notFor.map(humanizeText),
    sourceFields: product.sourceFields ? {
      ...product.sourceFields,
      title: humanizeText(product.sourceFields.title),
      mainCategory: humanizeText(product.sourceFields.mainCategory),
      store: humanizeText(product.sourceFields.store),
      brand: humanizeText(product.sourceFields.brand),
      features: product.sourceFields.features.map(humanizeText),
      description: product.sourceFields.description.map(humanizeText),
      details: humanizeDetails(product.sourceFields.details),
    } : undefined,
  };
}

export function humanizeRecommendationResult(result: RecommendationResult): RecommendationResult {
  return {
    ...result,
    excludedProducts: result.excludedProducts.map((item) => ({
      ...item,
      product: humanizeProduct(item.product),
      reason: humanizeText(item.reason),
    })),
    primaryRecommendation: result.primaryRecommendation ? humanizeRecommendationProduct(result.primaryRecommendation) : null,
    alternatives: result.alternatives.map(humanizeRecommendationProduct),
    regretGuard: humanizeText(result.regretGuard),
    evidenceSummary: humanizeText(result.evidenceSummary),
  };
}

function humanizeRecommendationProduct(item: RecommendationProduct): RecommendationProduct {
  return {
    ...item,
    product: humanizeProduct(item.product),
    reasons: item.reasons.map(humanizeText),
    cautions: item.cautions.map(humanizeText),
    regretGuard: humanizeText(item.regretGuard),
    priceAnalysis: {
      ...item.priceAnalysis,
      explanation: humanizeText(item.priceAnalysis.explanation),
    },
    evidence: item.evidence.map(humanizeEvidence),
    relevantRisks: item.relevantRisks.map(humanizeEvidence),
  };
}

function humanizeEvidence(item: RecommendationEvidence): RecommendationEvidence {
  return {
    ...item,
    title: humanizeText(item.title),
    detail: humanizeText(item.detail),
    source: humanizeText(item.source),
  };
}

function humanizeReview(review: Review): Review {
  return {
    ...review,
    sourceName: humanizeText(review.sourceName),
    content: humanizeText(review.content),
    usageDuration: humanizeText(review.usageDuration),
    userProfile: humanizeText(review.userProfile),
    topics: review.topics.map(humanizeText),
  };
}

function humanizeDiscussion(discussion: Discussion): Discussion {
  return {
    ...discussion,
    sourceName: humanizeText(discussion.sourceName),
    content: humanizeText(discussion.content),
    topic: humanizeText(discussion.topic),
    userProfile: humanizeText(discussion.userProfile),
  };
}

function humanizeQuestion(question: ProductQuestion): ProductQuestion {
  return {
    ...question,
    question: humanizeText(question.question),
    answer: humanizeText(question.answer),
    topic: humanizeText(question.topic),
  };
}

function humanizeVideo(video: VideoEvidence): VideoEvidence {
  return {
    ...video,
    videoTitle: humanizeText(video.videoTitle),
    creator: humanizeText(video.creator),
    finding: humanizeText(video.finding),
  };
}

function humanizePriceHistory(point: PriceHistory): PriceHistory {
  return {
    ...point,
    promotionType: humanizeText(point.promotionType),
    source: humanizeText(point.source),
  };
}

function humanizeDetails(details: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(details).map(([key, value]) => {
    if (typeof value === 'string') return [key, humanizeText(value)];
    if (Array.isArray(value)) return [key, value.map((item) => typeof item === 'string' ? humanizeText(item) : item)];
    return [key, value];
  }));
}
