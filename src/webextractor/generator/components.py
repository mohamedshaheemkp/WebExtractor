from __future__ import annotations

from pathlib import Path
from webextractor.generator.react import ReactSyntaxEmitter
from webextractor.model.component import ComponentNode


class ComponentCodeGenerator:
    """Generates production-quality Next.js / React TypeScript components."""

    @staticmethod
    def generate_component(comp: ComponentNode, public_assets: dict[str, str] | None = None) -> tuple[str, str]:
        """Returns (component_file_name, component_tsx_code)."""
        name = ReactSyntaxEmitter.sanitize_identifier(comp.name)
        title = comp.props.get("title") or name
        description = comp.props.get("description") or comp.text_content or "Crafted with precision and modern design standards."
        category = comp.category.lower()

        # Find sample image if available
        sample_img = "/images/sample.jpg"
        if public_assets:
            for remote_url, local_pub in public_assets.items():
                if "/images/" in local_pub:
                    sample_img = local_pub
                    break

        if "navbar" in category or "nav" in name.lower():
            links = comp.props.get("links", ["Home", "Projects", "About", "Contact"])
            links_jsx = "\n".join(
                f'            <a href="#{link.lower()}" className="text-sm font-medium text-neutral-400 hover:text-white transition-colors duration-200">{link}</a>'
                for link in links
            )
            code = f"""import React from "react";

export default function {name}() {{
  return (
    <header className="sticky top-0 z-50 w-full backdrop-blur-md bg-neutral-950/80 border-b border-neutral-800/60">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <a href="/" className="font-bold text-lg tracking-tight text-white hover:opacity-80 transition-opacity">
          {title}
        </a>
        <nav className="hidden md:flex items-center space-x-8">
{links_jsx}
        </nav>
        <div className="flex items-center space-x-4">
          <a
            href="#contact"
            className="px-4 py-2 rounded-full text-xs font-semibold bg-white text-black hover:bg-neutral-200 transition-all duration-200 shadow-sm"
          >
            Get in Touch
          </a>
        </div>
      </div>
    </header>
  );
}}
"""
        elif "hero" in category or "hero" in name.lower():
            code = f"""import React from "react";

export default function {name}() {{
  return (
    <section className="relative min-h-[75vh] flex flex-col justify-center items-center text-center px-6 py-24 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-primary/10 via-transparent to-transparent pointer-events-none" />
      <div className="relative z-10 max-w-4xl mx-auto space-y-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium tracking-wide uppercase bg-neutral-800/80 text-neutral-300 border border-neutral-700/50">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Crafted Experience</span>
        </div>
        <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight text-white leading-[1.08]">
          {title}
        </h1>
        <p className="text-lg md:text-xl text-neutral-400 max-w-2xl mx-auto leading-relaxed">
          {description}
        </p>
        <div className="pt-4 flex flex-wrap justify-center gap-4">
          <a
            href="#projects"
            className="px-6 py-3 rounded-full text-sm font-semibold bg-white text-black hover:bg-neutral-200 transition-all shadow-lg hover:shadow-white/10"
          >
            Explore Projects
          </a>
          <a
            href="#about"
            className="px-6 py-3 rounded-full text-sm font-semibold bg-neutral-900 text-white border border-neutral-800 hover:bg-neutral-800 transition-all"
          >
            Learn More
          </a>
        </div>
      </div>
    </section>
  );
}}
"""
        elif "project" in category or "project" in name.lower() or "card" in category:
            code = f"""import React from "react";

export default function {name}() {{
  const projects = [
    {{
      title: "Design System & Platform",
      category: "Interactive Engineering",
      description: "Scalable component architecture with high-fidelity micro-interactions.",
    }},
    {{
      title: "Digital Product Experience",
      category: "Interface Design",
      description: "Dynamic responsive views optimized for performance and immersion.",
    }},
    {{
      title: "Creative Technology Studio",
      category: "Motion & 3D",
      description: "Visual storytelling through modern fluid web typography.",
    }}
  ];

  return (
    <section id="projects" className="py-24 px-6 max-w-7xl mx-auto">
      <div className="space-y-4 mb-14">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Selected Works</p>
        <h2 className="text-3xl md:text-5xl font-bold tracking-tight text-white">{title}</h2>
        <p className="text-neutral-400 max-w-2xl">{description}</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {{projects.map((proj, idx) => (
          <article
            key={{idx}}
            className="group relative rounded-2xl border border-neutral-800/80 bg-neutral-900/40 p-6 hover:border-neutral-700 transition-all duration-300 hover:-translate-y-1"
          >
            <div className="aspect-video w-full rounded-xl bg-neutral-800/60 mb-6 overflow-hidden flex items-center justify-center text-neutral-600 text-xs font-mono">
              [Preview Asset]
            </div>
            <p className="text-xs font-medium text-neutral-400 mb-2">{{proj.category}}</p>
            <h3 className="text-xl font-semibold text-white mb-2 group-hover:text-primary transition-colors">
              {{proj.title}}
            </h3>
            <p className="text-sm text-neutral-400 leading-relaxed">{{proj.description}}</p>
          </article>
        ))}}
      </div>
    </section>
  );
}}
"""
        elif "footer" in category or "footer" in name.lower():
            code = f"""import React from "react";

export default function {name}() {{
  return (
    <footer className="border-t border-neutral-900 bg-neutral-950 py-16 px-6">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8">
        <div className="space-y-2 text-center md:text-left">
          <p className="font-bold text-lg text-white">{title}</p>
          <p className="text-xs text-neutral-500">© {{new Date().getFullYear()}} Reconstructed with WebExtractor.</p>
        </div>
        <div className="flex items-center space-x-6 text-sm text-neutral-400">
          <a href="#" className="hover:text-white transition-colors">Privacy</a>
          <a href="#" className="hover:text-white transition-colors">Terms</a>
          <a href="#" className="hover:text-white transition-colors">Twitter</a>
          <a href="#" className="hover:text-white transition-colors">GitHub</a>
        </div>
      </div>
    </footer>
  );
}}
"""
        else:
            # Generic section (About, Capabilities, Voice, Journey, Toolkit)
            code = f"""import React from "react";

export default function {name}() {{
  return (
    <section className="py-20 px-6 max-w-7xl mx-auto border-t border-neutral-900/60">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-12 items-start">
        <div className="md:col-span-4 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-neutral-500">Feature Section</p>
          <h2 className="text-3xl font-bold tracking-tight text-white">{title}</h2>
        </div>
        <div className="md:col-span-8 space-y-6 text-neutral-300 leading-relaxed">
          <p className="text-base md:text-lg text-neutral-400">
            {description}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4">
            <div className="p-5 rounded-xl bg-neutral-900/50 border border-neutral-800">
              <h4 className="font-semibold text-white mb-1">Interactive Detail</h4>
              <p className="text-sm text-neutral-400">Structured layout preserving semantic hierarchy.</p>
            </div>
            <div className="p-5 rounded-xl bg-neutral-900/50 border border-neutral-800">
              <h4 className="font-semibold text-white mb-1">Tailwind Design</h4>
              <p className="text-sm text-neutral-400">Configured with extracted design tokens.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}}
"""

        return f"{name}.tsx", code
