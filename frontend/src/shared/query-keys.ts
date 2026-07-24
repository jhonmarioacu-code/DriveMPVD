/**
 * Stable cache namespaces shared by features that need coordinated invalidation.
 * Feature-specific keys remain owned by each feature.
 */
export const queryNamespaces = {
  activity: ["activity"] as const,
  explorer: ["explorer"] as const,
};
