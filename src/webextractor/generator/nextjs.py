from __future__ import annotations

import json
import re
from pathlib import Path

from webextractor.analysis.site import SiteModel
from webextractor.generator.tokens import TokenCSSGenerator


class NextJSGenerator:

    def __init__(
        self,
        site: SiteModel,
        output_dir: str | Path,
    ):
        self.site = site
        self.output_dir = Path(
            output_dir
        )

    def generate(self) -> Path:

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._directories()

        self._package_json()

        self._layout()

        self._page()

        self._styles()

        self._site_model()

        self._analysis()

        return self.output_dir

    def _directories(self):

        for directory in [
            "app",
            "components",
            "public",
            "lib",
            "analysis",
        ]:
            (
                self.output_dir / directory
            ).mkdir(
                parents=True,
                exist_ok=True,
            )

    def _package_json(self):

        package = {
            "name": self._project_name(),
            "version": "0.1.0",
            "private": True,
            "scripts": {
                "dev": "next dev",
                "build": "next build",
                "start": "next start",
            },
            "dependencies": {
                "next": "latest",
                "react": "latest",
                "react-dom": "latest",
            },
        }

        self._write_json(
            self.output_dir
            / "package.json",
            package,
        )

    def _layout(self):

        content = """\
import "./globals.css";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
"""

        self._write(
            self.output_dir
            / "app"
            / "layout.tsx",
            content,
        )

    def _page(self):

        title = (
            self.site.title
            or "Reconstructed Website"
        )

        sections = self.site.dom.get(
            "sections",
            [],
        )

        section_components = []

        for index, section in enumerate(
            sections
        ):

            component_name = (
                self._component_name(
                    section,
                    index,
                )
            )

            self._component(
                component_name,
                section,
            )

            section_components.append(
                component_name
            )

        imports = "\n".join(
            f'import {name} from "../components/{name}";'
            for name in section_components
        )

        rendered = "\n".join(
            f"      <{name} />"
            for name in section_components
        )

        content = f"""\
{imports}

export default function Home() {{
  return (
    <main>
      <div className="site-header">
        <p>Reconstructed by WebExtractor</p>
      </div>

{rendered}
    </main>
  );
}}
"""

        self._write(
            self.output_dir
            / "app"
            / "page.tsx",
            content,
        )

    def _component(
        self,
        name: str,
        section: dict,
    ):

        text = section.get(
            "text_preview",
            "",
        )

        content = f"""\
export default function {name}() {{
  return (
    <section className="reconstructed-section">
      <div className="section-content">
        <span className="section-label">
          {section.get("element", "section").upper()}
        </span>

        <p>
          {self._escape(text)}
        </p>
      </div>
    </section>
  );
}}
"""

        self._write(
            self.output_dir
            / "components"
            / f"{name}.tsx",
            content,
        )

    def _styles(self):

        design_tokens = getattr(self.site, "design_system", None) or self.site.tokens or {}
        TokenCSSGenerator().generate(
            design_tokens,
            self.output_dir / "app" / "tokens.css",
        )

        content = """\
@import "./tokens.css";

* {
  box-sizing: border-box;
}

html,
body {
  margin: 0;
  padding: 0;
}

body {
  background: var(--color-2, var(--color-1, #080808));
  color: var(--color-1, #f5f5f5);
  font-family:
    Arial,
    Helvetica,
    sans-serif;
}

main {
  width: 100%;
}

.site-header {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  padding: 20px 32px;
  z-index: 100;
  pointer-events: none;
}

.site-header p {
  margin: 0;
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.5;
}

.reconstructed-section {
  min-height: 100vh;
  display: flex;
  align-items: center;
  padding: 100px 8vw;
}

.section-content {
  max-width: 1200px;
}

.section-label {
  display: block;
  margin-bottom: 24px;
  font-size: 11px;
  letter-spacing: 0.15em;
  opacity: 0.45;
}

.section-content p {
  margin: 0;
  max-width: 900px;
  font-size: clamp(24px, 4vw, 64px);
  line-height: 1.05;
}
"""

        self._write(
            self.output_dir
            / "app"
            / "globals.css",
            content,
        )

    def _site_model(self):

        self.site.save(
            self.output_dir
            / "analysis"
            / "site.json",
        )

    def _analysis(self):

        if self.site.tokens:
            self._write_json(
                self.output_dir
                / "analysis"
                / "tokens.json",
                self.site.tokens,
            )

        analysis = {
            "url": self.site.url,
            "title": self.site.title,
            "routes": self.site.routes,
            "resource_counts": {
                key: len(value)
                for key, value in self.site.assets.items()
            },
            "network_requests": len(
                self.site.network
            ),
            "sections": len(
                self.site.dom.get(
                    "sections",
                    [],
                )
            ),
            "headings": len(
                self.site.dom.get(
                    "headings",
                    [],
                )
            ),
            "links": len(
                self.site.dom.get(
                    "links",
                    [],
                )
            ),
            "tokens_extracted": {
                "colors": len(self.site.tokens.get("colors", [])) if self.site.tokens else 0,
                "radii": len(self.site.tokens.get("radii", [])) if self.site.tokens else 0,
            }
        }

        self._write_json(
            self.output_dir
            / "analysis"
            / "summary.json",
            analysis,
        )

    def _component_name(
        self,
        section: dict,
        index: int,
    ):

        element = section.get(
            "element",
            "section",
        )

        identifier = (
            section.get("id")
            or f"{element}_{index + 1}"
        )

        identifier = re.sub(
            r"[^a-zA-Z0-9]+",
            " ",
            identifier,
        )

        words = identifier.split()

        name = "".join(
            word.capitalize()
            for word in words
        )

        if not name:
            name = f"Section{index + 1}"

        return name

    def _project_name(self):

        parsed = re.sub(
            r"[^a-zA-Z0-9]+",
            "-",
            self.site.url,
        )

        return (
            parsed.strip("-").lower()
            + "-reconstructed"
        )

    @staticmethod
    def _escape(value: str):
        return (
            value
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    @staticmethod
    def _write(
        path: Path,
        content: str,
    ):
        path.write_text(
            content,
            encoding="utf-8",
        )

    @staticmethod
    def _write_json(
        path: Path,
        data,
    ):
        path.write_text(
            json.dumps(
                data,
                indent=2,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def generate_layout(site_name: str) -> str:
        return f"""import type {{ Metadata }} from "next";
import "./globals.css";

export const metadata: Metadata = {{
  title: "{site_name} — Reconstructed Experience",
  description: "Generated by WebExtractor reverse-engineering engine.",
}};

export default function RootLayout({{
  children,
}}: Readonly<{{
  children: React.ReactNode;
}}>) {{
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased selection:bg-primary selection:text-white">
        {{children}}
      </body>
    </html>
  );
}}
"""

    @staticmethod
    def generate_page(components: list[Any]) -> str:
        imports = []
        jsx_elements = []

        for comp in components:
            ident = comp.name if hasattr(comp, "name") else str(comp)
            imports.append(f'import {ident} from "../components/{ident}";')
            jsx_elements.append(f"      <{ident} />")

        imports_str = "\n".join(imports)
        jsx_str = "\n".join(jsx_elements)

        return f"""import React from "react";
{imports_str}

export default function Home() {{
  return (
    <main className="flex flex-col min-h-screen">
{jsx_str}
    </main>
  );
}}
"""

    @staticmethod
    def generate_sub_page(route_name: str) -> str:
        return f"""import React from "react";
import Navbar from "../../components/Navbar";
import Footer from "../../components/Footer";

export default function {route_name.replace(' ', '')}Page() {{
  return (
    <main className="flex flex-col min-h-screen">
      <Navbar />
      <section className="flex-1 py-24 px-6 max-w-7xl mx-auto space-y-6">
        <h1 className="text-4xl font-bold tracking-tight text-white">{route_name}</h1>
        <p className="text-neutral-400">Reconstructed route view for {route_name}.</p>
      </section>
      <Footer />
    </main>
  );
}}
"""

    @staticmethod
    def generate_next_config() -> str:
        return """/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
"""

    @staticmethod
    def generate_tsconfig() -> str:
        return """{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [
      {
        "name": "next"
      }
    ],
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
"""

