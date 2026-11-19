# 经营工作台

一个在本机运行的预算与实际经营分析工具。支持导入 Excel 预算、销售和费用数据，检查表格格式及计算结果，查看预算与实际对比，导出 Excel 报表和离线看板。

桌面端使用 Electron，界面使用 React 和 Vite，后端使用 FastAPI 和 SQLite。桌面菜单「经营工作台 → 界面样式」可在经典版 V1 和新版 V2 之间切换。

## 从源码运行

准备 Git、Node.js 22.12 或以上版本，以及 Python 3.13 或 3.14。

```bash
git clone https://github.com/liyuliang1004-gif/budget-workbench-open-source.git
cd budget-workbench-open-source
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
npm ci
npm run desktop
```

Windows PowerShell 下可用 `py -3.13 -m venv .venv` 创建环境，再运行 `.\.venv\Scripts\Activate.ps1`。其余安装和启动命令相同。

首次在桌面端启动时，选择一个独立目录保存 SQLite 数据库、配置、上传文件和导出结果。可以在「文件上传」下载空白预算模板和带示例行的实际经营模板。

也可以用浏览器打开工作台。先运行 `npm run build:v2`，再用虚拟环境运行 `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`。访问 [经典版 V1](http://127.0.0.1:8000/index.html) 或 [新版 V2](http://127.0.0.1:8000/index_v2.html)。浏览器启动方式默认使用仓库下的 `data/`，也可通过 `BUDGET_WORKBENCH_DATA_DIR` 指定目录。

AI 分析是可选功能，可在「系统设置」配置自己的 DeepSeek 凭据和服务地址。启用后，AI 分析请求会把用于分析的经营数据发送给所配置的服务。

## 本机只读 API 与 MCP

软件运行期间，从菜单「经营工作台 → 只读数据接口」复制当前地址。REST 入口为 `/api/read-only`，MCP 入口为 `/mcp`，采用 Streamable HTTP。可查询经营汇总、预算销售与费用、实际销售与费用。接口仅供同一台电脑的软件访问。

参阅 [只读接口对接说明](docs/给其他软件Codex的只读接口对接指令.md)。

## 测试与打包

```bash
python -m pytest backend/tests -q
npm run desktop:test
npm run build:v2
```

在对应平台执行 `npm run desktop:dmg`（macOS）或 `npm run desktop:win`（Windows，需先激活 Python 虚拟环境）。公开仓库中的 Windows 工作流也可手动触发，构建结果可在对应运行记录中下载。

## 许可证

项目源码使用 [MIT 许可证](LICENSE)。
