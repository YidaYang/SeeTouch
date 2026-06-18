# 贡献指南

感谢你考虑为 SeeTouch 贡献代码！

---

## 贡献方式

### 报告 Bug

在 [GitHub Issues](https://github.com/your-username/seetouch/issues) 提交 Bug 报告时，请包含：

- **环境信息**：Python 版本、操作系统、手机型号/Android 版本
- **复现步骤**：详细的操作流程
- **期望行为** vs **实际行为**
- **日志输出**：`./runs/<timestamp>/` 目录下的日志文件
- **截图**（如适用）

### 功能建议

提交功能请求时，请说明：
- **使用场景**：解决什么问题
- **预期效果**：希望如何使用
- **替代方案**（如果有）

### 提交代码

1. **Fork 仓库**  
   点击右上角 Fork 按钮

2. **克隆到本地**
   ```bash
   git clone https://github.com/your-username/seetouch.git
   cd seetouch
   ```

3. **创建分支**  
   使用语义化分支名：
   ```bash
   git checkout -b feature/add-web-controller
   git checkout -b fix/open-app-crash
   git checkout -b docs/improve-readme
   ```

4. **安装开发环境**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
   pip install -e ".[dev]"
   ```

5. **编写代码**  
   - 遵循现有代码风格
   - 添加必要的测试
   - 更新文档（如适用）

6. **运行测试**
   ```bash
   # 代码检查
   ruff check seetouch/
   ruff format seetouch/

   # 单元测试
   pytest tests/ -v

   # 覆盖率
   pytest --cov=seetouch --cov-report=term-missing
   ```

7. **提交更改**  
   使用规范的 commit message：
   ```bash
   git add .
   git commit -m "feat: add web controller support"
   git commit -m "fix: resolve OPEN app crash on MIUI"
   git commit -m "docs: update installation guide"
   ```

   **Commit 类型**：
   - `feat`: 新功能
   - `fix`: Bug 修复
   - `docs`: 文档更新
   - `test`: 测试相关
   - `refactor`: 代码重构
   - `perf`: 性能优化
   - `chore`: 构建/工具链更新

8. **推送分支**
   ```bash
   git push origin feature/add-web-controller
   ```

9. **创建 Pull Request**  
   在 GitHub 上点击 "New Pull Request"，填写：
   - **标题**：简明扼要（如 commit message）
   - **描述**：
     - 解决了什么问题（关联 Issue 编号）
     - 如何解决的（关键设计决策）
     - 测试覆盖（真机验证/单元测试通过情况）
     - 截图/演示（如适用）

---

## 代码规范

### Python 风格

- 遵循 PEP 8（由 Ruff 自动检查）
- 使用类型注解（`from __future__ import annotations`）
- 函数/类添加 docstring（Google 风格）

示例：
```python
def normalize_point(x: int, y: int, width: int, height: int) -> tuple[int, int]:
    """将像素坐标归一化到 0-1000 区间。

    Args:
        x: 像素 x 坐标
        y: 像素 y 坐标
        width: 屏幕宽度
        height: 屏幕高度

    Returns:
        (归一化 x, 归一化 y) 元组
    """
    return int(x * 1000 / width), int(y * 1000 / height)
```

### 测试要求

- 新功能必须包含单元测试
- 测试文件放在 `tests/` 目录，命名为 `test_<module>.py`
- 使用 pytest fixtures 复用测试环境
- Mock 外部依赖（VLM API、设备控制）

示例：
```python
import pytest
from seetouch.core.action import Action, parse_action

def test_parse_click_action():
    result = parse_action('{"action": "CLICK", "parameters": {"point": [500, 300]}}')
    assert result.action == "CLICK"
    assert result.parameters["point"] == [500, 300]

def test_parse_invalid_action_fallback_to_wait():
    result = parse_action('{"action": "INVALID"}')
    assert result.action == "WAIT"  # fallback
```

### 模块化设计

新增功能时遵循现有分层：

- **device/** — 设备控制（Android / Web / Desktop）
- **reasoning/** — VLM 推理（Doubao / Claude / GPT-4V）
- **perception/** — 视觉处理（坐标转换、图像编码）
- **safety/** — 安全防护（敏感动作识别）
- **core/** — 核心逻辑（Task / Action / Runner / Session）

新增 VLM 后端示例：
```python
# seetouch/reasoning/claude.py
from .base import Reasoner, ReasoningResult

class ClaudeReasoner(Reasoner):
    def reason(self, screenshot, task, history) -> ReasoningResult:
        # 实现 Claude API 调用
        ...
```

---

## 真机测试

提交涉及设备控制或推理逻辑的 PR 时，建议提供真机验证结果：

```bash
python -m seetouch run "你的测试指令"
```

在 PR 描述中附上：
- 设备信息（型号 / Android 版本）
- 任务步数 / 耗时
- `./runs/<timestamp>/report.json` 内容摘要

---

## 文档更新

文档与代码同样重要！

- **README.md** — 用户使用指南、快速开始
- **代码注释** — 复杂逻辑、设计决策、已知限制
- **CHANGELOG.md**（如适用）— 版本更新记录

---

## 行为准则

- **尊重他人**：友善、包容、建设性反馈
- **开放讨论**：欢迎不同意见，通过讨论达成共识
- **质量优先**：宁可多花时间完善，不要匆忙提交半成品

---

## 获取帮助

遇到问题？

- **Discussions**: [GitHub Discussions](https://github.com/your-username/seetouch/discussions) — 技术讨论、使用交流
- **Issues**: [GitHub Issues](https://github.com/your-username/seetouch/issues) — Bug 报告、功能请求

---

## 许可协议

提交代码即表示同意以 [Apache License 2.0](LICENSE) 开源。

---

**感谢你的贡献！每一个 PR 都让 SeeTouch 变得更好。** 🎉
