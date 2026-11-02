import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['node_modules', 'dist', '../src/huggingface_agents_langgraph/static'] },
  js.configs.recommended,
  ...tseslint.configs.strict,
  reactHooks.configs.flat.recommended,
  jsxA11y.flatConfigs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: { globals: { ...globals.browser } },
    rules: {
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/no-non-null-assertion': 'error',
    },
  },
  // Hexagonal direction: inner layers know nothing of the outer ones.
  ...[
    ['src/domain/**', ['adapters', 'application', 'ports', 'ui', 'app']],
    ['src/application/**', ['adapters', 'ui', 'app']],
    ['src/ports/**', ['adapters', 'application', 'ui', 'app']],
    ['src/adapters/**', ['ui', 'app']],
    ['src/ui/**', ['adapters', 'app']],
  ].map(([layer, forbidden]) => ({
    files: [layer],
    ignores: ['**/*.test.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: forbidden.map((target) => ({
            regex: `(^|/)${target}(/|$)`,
            message: `${layer.replace('/**', '')} must not depend on ${target}.`,
          })),
        },
      ],
    },
  })),
  // Size gate. The files listed in the override below were already over the limit
  // before the gate existed; split them and remove them from the list, never add.
  {
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['**/*.test.{ts,tsx}'],
    rules: {
      'max-lines': ['error', { max: 450, skipBlankLines: true, skipComments: true }],
      complexity: ['error', 20],
    },
  },
  {
    // Message catalogues are data, not logic.
    files: ['src/i18n/messages.*.ts'],
    rules: { 'max-lines': 'off' },
  },
  {
    files: ['src/ui/editor/EditorWorkspace.tsx'],
    rules: { 'max-lines': 'off' },
  },
  {
    // Pages that grew too branchy; split into subcomponents in the refactoring (F1).
    files: [
      'src/ui/editor/EditorWorkspace.tsx',
      'src/ui/editor/nodes.tsx',
      'src/ui/experiments/ExperimentsPage.tsx',
      'src/ui/run/RunsPage.tsx',
    ],
    rules: { complexity: 'off' },
  },
  {
    files: ['**/*.test.{ts,tsx}', 'src/test/**', 'scripts/**', 'eslint.config.js'],
    languageOptions: { globals: { ...globals.node } },
  },
  prettier,
);
