# DXF Sheet Explorer

面向建筑施工图的 DXF 图框识别、拆图和 Web 浏览原型。

## 已验证的样例

当前样例 DXF 已在本地完成真实解析：

- DXF 版本：`AC1032`
- 原始文件大小：`41,415,351 bytes`
- 标准图框：`27`
- 施工图目录：`1`
- 正式施工图：`J01`–`J26`，共 `26` 张
- 未归入图框的模型空间实体：`2`

`data/manifest.json` 已包含 26 张图纸的图号、图名、图框坐标、实体数量和拆分文件名。

## 项目结构

```text
backend/              FastAPI API
data/manifest.json    已解析的 26 张图纸清单
data/source/          原始 DXF（默认不提交大文件）
data/sheets/          拆分后的 J01-J26 DXF（默认不提交大文件）
frontend/             React + TypeScript + Vite
tools/split_dxf.py    图框识别与拆图工具
```

## 1. 放入原始 DXF

将原始文件保存为：

```text
data/source/original.dxf
```

## 2. 拆分 26 张图纸

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r backend/requirements.txt
python tools/split_dxf.py data/source/original.dxf
```

脚本会识别标准图框与图签块，排除施工图目录，并生成：

```text
data/sheets/J01_*.dxf
...
data/sheets/J26_*.dxf
data/manifest.json
```

## 3. 启动后端

```bash
uvicorn backend.app.main:app --reload --port 8000
```

API：

- `GET /api/health`
- `GET /api/sheets`
- `GET /api/sheets/{sheet_no}`
- `GET /api/sheets/{sheet_no}/entities`

## 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173`。

## 当前阶段

第一版重点是把 DXF 数据链路跑通：**原始 DXF → 图框识别 → J01-J26 拆图 → API → Web CAD 风格浏览器**。前端已预留图层开关和实体渲染，下一阶段会补充更完整的 ARC/SPLINE/HATCH 渲染、鼠标框选、拖拽平移、缩放、构件关系分析等能力。
