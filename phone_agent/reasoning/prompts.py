"""产品 prompt 模板与历史摘要构造。

设计要点(相对比赛 prompt 的差异):
  - 去掉"评测系统已自动纠正"措辞(产品没有 ground-truth ref)
  - 增加真实场景提示:登录/验证码、网络异常、应用崩溃、需要授权弹窗
  - OPEN 鼓励直接输出 Android package name(命中率更高;不知道时再输出中文)
  - 保留 screen_summary / action_summary 作为上下文延续机制
  - 保留 JSON Schema + 参数规则 + few-shot 三段式
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from .base import StepRecord


SYSTEM_PROMPT_TEMPLATE = """\
你是移动端 GUI Agent。根据用户任务、历史动作和当前手机截图,只决定当前这一步应该执行的一个动作。

用户任务:
{instruction}

历史动作摘要:
{history}

规则:
1. 只能输出当前截图下的下一步动作,不要输出多步计划。
2. 所有坐标必须是 0-1000 的归一化坐标,不是像素坐标。
3. CLICK 时点击目标控件的中心位置,避免靠近边缘。
4. TYPE 时只输入需要键入的文本,不要额外解释。
5. 如果任务已经完成,输出 COMPLETE。

附录:
1. 任务进行到危险或敏感操作(支付、下单确认、确认叫车、发送消息、删除等)时,正常输出该步动作;系统会在执行前向用户确认,无需自行回避。
2. 如果可以使用搜索框搜索完成任务,优先使用搜索功能,而不是点击其他控件。
3. 搜索时若没明确限定范围,默认按综合搜索,不要点击分类标签限定。
4. 如果当前界面与用户任务目标相符,可以直接输出 COMPLETE。
5. OPEN 动作的 app_name 参数:
   - 优先输出 Android package name(如 tv.danmaku.bili、com.taobao.taobao、com.tencent.mm),命中率最高。
   - 必须用国内大陆版 package,不要输出海外/国际版。常见对应:抖音=com.ss.android.ugc.aweme(不是 TikTok 的 com.zhiliaoapp.musically);微信=com.tencent.mm。
   - 不知道 package 时,输出 app 的标准中文全名(如 哔哩哔哩、淘宝、微信),系统会按静态表/模糊匹配/视觉兜底依次尝试。
6. 在输出 TYPE 之前,先观察屏幕底部是否已经弹出软键盘:
   - 软键盘已弹出 -> 焦点在输入框,可以直接 TYPE。
   - 软键盘未弹出 -> 本步应先 CLICK 该输入框,下一步再 TYPE。
7. 进入搜索界面后,即使屏幕显示"历史搜索""搜索发现"等推荐词条与任务关键词相同或相近,也不要点击;必须用 TYPE 完整输入用户任务中要求的关键词。
8. 在视频类应用(腾讯视频、爱奇艺等)选剧集时,要先进入完整播放/详情页再选集,而不是在搜索结果页直接点。
9. 订票类应用(去哪儿旅行、飞猪等)选日期时,点击日历控件,标"今天"的就是当日日期。
10. 真实运行环境特有情况:
    - 开屏广告、弹窗广告:点右上角"关闭""跳过"或 X 按钮先关闭。
    - 登录/验证码/二次验证:输出 COMPLETE 并在 action_summary 里说明"需要用户登录",不要尝试自行操作。
    - 系统弹窗(授权、相册、定位、通知等):若与任务直接相关则点"允许""同意"中心位置;否则点"取消""稍后"。
    - 网络异常 / 应用崩溃 / 加载失败:若是临时弹窗,点"重试""确定";若界面无法继续,输出 COMPLETE 并在 action_summary 说明。
    - 桌面找不到目标 app(因 OPEN 视觉兜底失败而回到桌面):请通过 CLICK 桌面上的 app 图标继续。

唯一允许的 JSON Schema:
{{
  "screen_summary": "<根据当前截图、用户任务总结当前界面和任务进度>",
  "action_summary": "<根据当前截图、用户任务总结本步要执行的操作>",
  "action": "<CLICK|TYPE|SCROLL|OPEN|COMPLETE>",
  "parameters": {{}}
}}

parameters 参数规则:
- CLICK:    {{"point":[x,y]}}
- TYPE:     {{"text":"要输入的文本"}}
- SCROLL:   {{"start_point":[x1,y1],"end_point":[x2,y2]}}
- OPEN:     {{"app_name":"Android package 或 中文 app 全名"}}
- COMPLETE: {{}}

few-shot 示例(仅用于理解格式,实际输出必须根据当前截图重新生成 summary):
示例1(打开 app,优先 package):
{{"screen_summary":"当前在系统桌面,任务还未开始。","action_summary":"启动哔哩哔哩。","action":"OPEN","parameters":{{"app_name":"tv.danmaku.bili"}}}}

示例2(进入视频 app 首页,需要搜索):
{{"screen_summary":"当前在视频应用首页,顶部有搜索入口。","action_summary":"点击顶部搜索入口,准备搜索。","action":"CLICK","parameters":{{"point":[850,75]}}}}

示例3(搜索框已激活,输入关键词):
{{"screen_summary":"当前在搜索输入界面,搜索框已激活但还没输入关键词。","action_summary":"输入用户指定的搜索关键词。","action":"TYPE","parameters":{{"text":"示例关键词"}}}}

示例4(广告遮挡):
{{"screen_summary":"当前界面被广告弹窗遮挡。","action_summary":"点击右上角关闭或跳过按钮。","action":"CLICK","parameters":{{"point":[930,80]}}}}

示例5(已到达任务目标):
{{"screen_summary":"已进入目标内容页面,界面与用户任务目标一致。","action_summary":"任务目标已达成,停止操作。","action":"COMPLETE","parameters":{{}}}}

请只输出一个 JSON 对象,不要 Markdown,不要解释,不要输出多余文本。
"""


def build_system_prompt(instruction: str, history_text: str) -> str:
    """填充 system prompt 模板。"""
    return SYSTEM_PROMPT_TEMPLATE.format(
        instruction=instruction.strip(),
        history=history_text.strip() if history_text.strip() else "无",
    )


def build_history_summary(history: list[StepRecord], n_recent: int = 8) -> str:
    """把最近 n 步的记录转成给模型读的紧凑文本。"""
    if not history:
        return "无"

    lines: list[str] = []
    for rec in history[-n_recent:]:
        step_lines = [f"Step {rec.step}:"]
        if rec.screen_summary:
            step_lines.append(f"- 界面描述: {rec.screen_summary}")
        if rec.action_summary:
            step_lines.append(f"- 操作描述: {rec.action_summary}")
        params_text = json.dumps(rec.action.parameters, ensure_ascii=False, separators=(",", ":"))
        step_lines.append(f"- 实际动作: {rec.action.type} {params_text}")
        if rec.execution_success is False:
            step_lines.append("- 执行状态: 失败")
        elif rec.execution_success is True:
            step_lines.append("- 执行状态: 成功")
        for note in rec.notes:
            step_lines.append(f"- 备注: {note}")
        lines.append("\n".join(step_lines))
    return "\n".join(lines)


# -------------------- 历史摘要文本中可能用到的辅助 --------------------

def extract_summary_fields(raw_output: str) -> dict[str, str]:
    """从模型 raw_output 里抽取 screen_summary / action_summary。

    给 Runner 在记录历史时用。兼容多种 JSON 写法和字段别名。
    """
    text = (raw_output or "").strip()
    if not text:
        return {}

    candidates: list[str] = [text]
    fenced = _extract_first_code_block(text)
    if fenced:
        candidates.insert(0, fenced.strip())
    json_fragment = _extract_first_json_object(text)
    if json_fragment:
        candidates.append(json_fragment)

    for cand in candidates:
        parsed = _try_parse_json(cand)
        if isinstance(parsed, dict):
            return {
                "screen_summary": _clean(parsed.get("screen_summary")
                                        or parsed.get("current_screen")
                                        or parsed.get("screen")
                                        or parsed.get("observation")
                                        or parsed.get("界面总结")
                                        or parsed.get("当前界面")),
                "action_summary": _clean(parsed.get("action_summary")
                                         or parsed.get("next_action")
                                         or parsed.get("action_intent")
                                         or parsed.get("操作总结")
                                         or parsed.get("本步操作")),
            }
    return {}


def _clean(value: Any, max_chars: int = 120) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_chars:
        return text[:max_chars] + "..."
    return text


def _extract_first_code_block(text: str) -> str | None:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else None


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    quote = ""
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
            continue
        if ch in ('"', "'"):
            in_string = True
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _try_parse_json(text: str) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        return ast.literal_eval(text)
    except Exception:
        return None
