from __future__ import annotations

import json
from webextractor.model.token import DesignTokens


class StylesGenerator:
    """Generates Tailwind config, PostCSS config, and globals.css."""

    @staticmethod
    def generate_tailwind_config(tokens: DesignTokens) -> str:
        color_map = {}
        for col in tokens.colors:
            color_map[col.name] = col.value

        colors_json = json.dumps(color_map, indent=8)[8:-2]

        return f"""import type {{ Config }} from "tailwindcss";

const config: Config = {{
  content: [
    "./app/**/*.{{js,ts,jsx,tsx,mdx}}",
    "./components/**/*.{{js,ts,jsx,tsx,mdx}}",
  ],
  theme: {{
    extend: {{
      colors: {{
{colors_json}
      }},
    }},
  }},
  plugins: [],
}};

export default config;
"""

    @staticmethod
    def generate_globals_css(tokens: DesignTokens) -> str:
        css_vars = []
        for col in tokens.colors:
            css_vars.append(f"  --{col.name}: {col.value};")
        vars_block = "\n".join(css_vars)

        return f"""@tailwind base;
@tailwind components;
@tailwind utilities;

:root {{
{vars_block}
}}

html,
body {{
  padding: 0;
  margin: 0;
  background-color: #080808;
  color: #f3f3f3;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Open Sans", "Helvetica Neue", sans-serif;
  overflow-x: hidden;
  scroll-behavior: smooth;
}}

/* Custom scrollbar */
::-webkit-scrollbar {{
  width: 8px;
}}
::-webkit-scrollbar-track {{
  background: #0d0d0d;
}}
::-webkit-scrollbar-thumb {{
  background: #262626;
  border-radius: 4px;
}}
::-webkit-scrollbar-thumb:hover {{
  background: #404040;
}}
"""

    @staticmethod
    def generate_postcss_config() -> str:
        return """module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
"""
