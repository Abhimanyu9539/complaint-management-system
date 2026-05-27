/**
 * Openers offered on the empty chat screen. They live here rather than beside
 * the mock answers so the live path does not import the mock corpus — but they
 * are still written to match what the seeded knowledge base can answer.
 */
export const SUGGESTED_PROMPTS: string[] = [
  'My ProBlend 300 is showing ERR-22 and won\'t start — is this covered?',
  'Customer says their toaster started smoking, what do I do?',
  'A customer wants a refund because their order arrived 9 days late.',
  'How do I decide which department a complaint should be routed to?',
];
