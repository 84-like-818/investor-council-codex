#!/usr/bin/env python3
from pathlib import Path
import argparse, re

PRESETS = {
    "chat": {
        "name": "对话助手",
        "goal": "像这个人物一样与你讨论问题，重在启发、辨析、认知提升。",
        "structure": "1. 核心判断\n2. 为什么这样看\n3. 你最容易忽略的地方\n4. 一个追问"
    },
    "market-memo": {
        "name": "市场备忘录",
        "goal": "把这个人物的框架转成对当前市场的简洁分析备忘录。",
        "structure": "1. 市场状态\n2. 关键证据\n3. 人物判断\n4. 触发条件\n5. 失效条件\n6. 不做什么"
    },
    "journal-review": {
        "name": "交易复盘",
        "goal": "用这个人物的标准审视你的动作、错误、犹豫和执行缺陷。",
        "structure": "1. 你做对了什么\n2. 你做错了什么\n3. 根因\n4. 以后怎么防\n5. 一句最尖锐的提醒"
    },
    "source-harvest": {
        "name": "资料采集与整理",
        "goal": "围绕这个人物，列出资料缺口、优先级和下一轮采集建议。",
        "structure": "1. 已有资料\n2. 缺失资料\n3. 最优先补的 5 项\n4. 哪些能进 doctrine\n5. 哪些只保留线索"
    }
}

def slugify(s: str) -> str:
    s = s.strip().lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "work"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--persona-slug", required=True)
    parser.add_argument("--work-mode", required=True, help="chat / market-memo / journal-review / source-harvest 或自定义")
    parser.add_argument("--work-mode-name", default="")
    parser.add_argument("--work-mode-goal", default="")
    parser.add_argument("--output-structure", default="")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    factory_root = Path(__file__).resolve().parent.parent
    persona_slug = slugify(args.persona_slug)
    work_mode = slugify(args.work_mode)
    skill_slug = f"{persona_slug}-{work_mode}"

    preset = PRESETS.get(work_mode, {})
    work_mode_name = args.work_mode_name or preset.get("name", work_mode)
    work_mode_goal = args.work_mode_goal or preset.get("goal", "基于该人物资料完成指定工作。")
    output_structure = args.output_structure or preset.get("structure", "1. 结论\n2. 依据\n3. 下一步")

    text = (factory_root / "templates" / "workmode-skill" / "SKILL.md.template").read_text(encoding="utf-8")
    text = text.replace("{{skill_slug}}", skill_slug)
    text = text.replace("{{persona_slug}}", persona_slug)
    text = text.replace("{{work_mode_name}}", work_mode_name)
    text = text.replace("{{work_mode_goal}}", work_mode_goal)
    text = text.replace("{{output_structure}}", output_structure)

    dst = repo_root / ".agents" / "skills" / skill_slug
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "SKILL.md").write_text(text, encoding="utf-8")
    print(f"已创建 work-mode skill: {dst / 'SKILL.md'}")

if __name__ == "__main__":
    main()
