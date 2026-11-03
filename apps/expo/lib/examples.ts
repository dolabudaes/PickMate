export type ChatExample = {
  label: string;
  prompt: string;
};

export type TasteExample = {
  phrase: string;
  hint: string;
  chipLabel: string;
  savedLabel: string;
};

/** Launch demo starters. */
export const chatExamples: ChatExample[] = [
  {
    label: 'I want wireless earbuds',
    prompt: 'I want affordable wireless earbuds for commuting and everyday listening.',
  },
  {
    label: 'I need a soundbar for my TV',
    prompt: 'I want a soundbar with clear dialogue for a small living room TV and simple setup.',
  },
  {
    label: 'I want compact desk speakers',
    prompt: 'I want compact desk speakers with a simple wired connection for everyday music and video calls.',
  },
];

export const tasteExamples: TasteExample[] = [
  {
    phrase: 'Compatibility matters more to me than the lowest price.',
    hint: 'Long-term shopping preference',
    chipLabel: 'Compatibility first',
    savedLabel: 'Compatibility first',
  },
  {
    phrase: 'I usually care more about value than brand.',
    hint: 'Long-term shopping preference',
    chipLabel: 'Value over brand',
    savedLabel: 'Value over brand',
  },
];
