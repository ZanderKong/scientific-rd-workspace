# Theme Settings

The current web app uses the theme registry in `src/components/themes/theme.config.ts`, the default provider in `src/components/themes/active-theme.tsx`, and tokens in `src/styles/themes/`.

To add a theme:

1. Add a token file under `src/styles/themes/`.
2. Import it from `src/styles/theme.css`.
3. Register its value and display name in `theme.config.ts`.
4. Add any required font variable in `font.config.ts`.
5. Verify the Settings appearance control in light and dark mode.

Theme choice is a browser preference. It is unrelated to Project scope, locale, scientific object data, authentication or user accounts. Settings supports system, light and dark appearance; do not add a separate theme selector route.
