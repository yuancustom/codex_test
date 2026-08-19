# DXF Sheet Explorer

面向建筑施工图的 DXF 图框识别、拆图和 Web CAD 浏览器原型。

## 已验证样例

当前样例 DXF 已真实解析：

- DXF 版本：`AC1032`
- 原始文件大小：`41,415,351 bytes`
- 原始文件 SHA-256：`52986d56d094ad7807c958d3d3411cbdf838f62f17ed6a626c8ba88a99bab38d`
- 标准图框：`27`
- 施工图目录：`1`
- 正式施工图：`J01`–`J26`，共 `26` 张
- 未归入图框的模型空间实体：`2`
- J01 顶层实体：`647`
- J01 展开块、标注和曲线后的 Web 可视实体：`1,474`

`data/manifest.json` 已包含 26 张图纸的图号、图名、图框坐标、实体数量和拆分文件名。

## 目录

```text
backend/                 FastAPI API
data/manifest.json       26 张图纸清单
data/source/             原始 DXF
data/sheets/             拆分后的 J01-J26 DXF
frontend/                React + TypeScript + Vite
tools/split_dxf.py       图框识别与拆图
tools/prepare_source.py  从 .gz/.xz 存档恢复原始 DXF
```

## 数据准备

原始文件路径：

```text
data/source/original.dxf
```

如果保存的是压缩存档，可先恢复并校验：

```bash
python tools/prepare_source.py data/source/original.dxf.gz \
  --sha256 52986d56d094ad7807c958d3d3411cbdf838f62f17ed6a626c8ba88a99bab38d
```

然后拆分 26 张图纸：

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
python tools/split_dxf.py data/source/original.dxf
```

生成：

```text
data/sheets/J01_*.dxf
...
data/sheets/J26_*.dxf
data/manifest.json
```

## 后端

```bash
uvicorn backend.app.main:app --reload --port 8000
```

API：

- `GET /api/health`
- `GET /api/source`
- `GET /api/sheets`
- `GET /api/sheets/{sheet_no}`
- `GET /api/sheets/{sheet_no}/entities?expand_blocks=true&limit=50000`

实体接口支持 LINE、POLYLINE、LWPOLYLINE、CIRCLE、ARC、TEXT、MTEXT、POINT、SOLID，并将 SPLINE/ELLIPSE 离散为曲线折线；INSERT/DIMENSION/LEADER 可展开为虚拟图元。

## 前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`。Vite 会将 `/api` 代理到 FastAPI。

当前交互：

- J01-J26 图纸切换
- CAD 图元 SVG 渲染
- 鼠标滚轮缩放
- 左键拖拽平移
- FIT 适配窗口
- 图层显隐 / 全部 / 清空
- 点击实体高亮并查看属性
- ARC 与曲线渲染
- 块、标注展开后渲染

## 状态

数据解析、26 张图纸识别、拆图和后端实体接口已用真实样例验证。前端源码已完成上述交互；当前执行容器无法访问 npm registry，因此依赖安装/build 需要在具备网络的环境运行后再做最终构建验证。
