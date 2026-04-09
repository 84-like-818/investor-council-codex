#!/usr/bin/env python3
from pathlib import Path
import argparse, json, shutil, re

def slugify(s: str) -> str:
    s = s.strip().lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        raise ValueError("slug 为空")
    return s

def replace(text: str, mapping: dict) -> str:
    for k, v in mapping.items():
        text = text.replace("{{" + k + "}}", v)
    return text

def copy_tree(src: Path, dst: Path):
    if dst.exists():
        raise FileExistsError(f"{dst} 已存在")
    shutil.copytree(src, dst)

def write_rendered_template(src: Path, dst: Path, mapping: dict):
    dst.parent.mkdir(parents=True, exist_ok=True)
    text = src.read_text(encoding="utf-8")
    dst.write_text(replace(text, mapping), encoding="utf-8")

def ensure_marketplace(repo_root: Path, slug: str, plugin_name: str, display_name: str):
    marketplace_path = repo_root / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    if marketplace_path.exists():
        data = json.loads(marketplace_path.read_text(encoding="utf-8"))
    else:
        data = {"name": "persona-skill-lab", "interface": {"displayName": "Persona Skill Lab"}, "plugins": []}

    existing = {p["name"]: p for p in data.get("plugins", [])}
    existing[plugin_name] = {
        "name": plugin_name,
        "source": {"source": "local", "path": f"./plugins/{plugin_name}"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
        "interface": {"displayName": display_name}
    }
    data["plugins"] = list(existing.values())
    marketplace_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--short-description", default="")
    parser.add_argument("--default-prompt", default="")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    factory_root = Path(__file__).resolve().parent.parent
    slug = slugify(args.slug)
    display_name = args.display_name.strip()
    role = args.role.strip()
    description = args.description.strip() or f"在与 {display_name} 对应的领域问题上触发。只在该人物擅长范围内回答。"
    short_description = args.short_description.strip() or role
    default_prompt = args.default_prompt.strip() or f"先读取 references，再以 {display_name} 的视角回答。"
    plugin_name = f"{slug}-assistant"

    mapping = {
        "slug": slug,
        "display_name": display_name,
        "role": role,
        "description": description,
        "short_description": short_description,
        "default_prompt": default_prompt,
        "plugin_name": plugin_name,
    }

    # create skill
    skill_dst = repo_root / ".agents" / "skills" / slug
    copy_tree(factory_root / "templates" / "base-skill", skill_dst)
    # render templates
    skill_template = skill_dst / "SKILL.md.template"
    write_rendered_template(skill_template, skill_dst / "SKILL.md", mapping)
    skill_template.unlink()

    yaml_template = skill_dst / "agents" / "openai.yaml.template"
    write_rendered_template(yaml_template, skill_dst / "agents" / "openai.yaml", mapping)
    yaml_template.unlink()

    # create plugin
    plugin_dst = repo_root / "plugins" / plugin_name
    copy_tree(factory_root / "templates" / "base-plugin", plugin_dst)
    plugin_manifest_template = plugin_dst / ".codex-plugin" / "plugin.json.template"
    write_rendered_template(plugin_manifest_template, plugin_dst / ".codex-plugin" / "plugin.json", mapping)
    plugin_manifest_template.unlink()

    # initial skill snapshot inside plugin
    plugin_skill_dst = plugin_dst / "skills" / slug
    shutil.copytree(skill_dst, plugin_skill_dst)

    ensure_marketplace(repo_root, slug, plugin_name, display_name)

    print(f"已创建 skill: {skill_dst}")
    print(f"已创建 plugin: {plugin_dst}")
    print("下一步：")
    print(f"1) 填写 {skill_dst / 'references'}")
    print(f"2) 运行: python scripts/sync_skill_to_plugin.py --repo-root {repo_root} --slug {slug}")
    print("3) 重启 Codex")

if __name__ == "__main__":
    main()
