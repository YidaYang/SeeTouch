# Phone Agent — Android GUI 自动化

把自然语言指令翻译成真机操作的 Agent 产品。

- 平台:Android(uiautomator2 驱动)
- 推理:Doubao Vision(可换);保留多模型抽象接口
- 形态:CLI MVP,自动连续执行 + 敏感动作前用户确认

## 安装

```powershell
cd phone_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## 准备 Android 设备

1. 用 USB 连接手机(开启开发者选项 + USB 调试)或配置无线 ADB
2. `adb devices` 应能看到设备
3. 初始化 uiautomator2(自动装 atx-agent 到手机):
   ```powershell
   python -m uiautomator2 init
   ```

## 配置 API Key

复制 `.env.example` 为 `.env`,填入:

```
VLM_API_KEY=你的火山方舟 API Key
# 可选:
# DOUBAO_MODEL_ID=doubao-seed-1-6-vision-250815
# DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3
```

## 自检

```powershell
python -m phone_agent.scripts.doctor
```

## 运行

```powershell
python -m phone_agent run "打开抖音"
python -m phone_agent run "在哔哩哔哩搜索采莲曲"
```

敏感任务(支付/下单/发送)会在关键步骤前停下问你。

## 目录结构

```
phone_agent/
├── core/         主循环、Action、Task、Session
├── device/       设备控制层(android/、未来 web/、desktop/)
├── perception/   截图与坐标转换
├── reasoning/    VLM 推理(prompts/parser/doubao)
├── safety/       敏感动作识别和拦截
├── cli/          命令行入口
├── scripts/      doctor、replay
└── tests/        单测和集成测试
```

## 开发

```powershell
pip install -e ".[dev]"
pytest tests/
```
